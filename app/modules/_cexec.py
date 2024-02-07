import base64
import json
import os
import subprocess
from enum import Enum
from typing import Any, Callable, Optional
import time

from fastapi import HTTPException
from models.faas import Param
from modules._executor import *
from modules._logger import CognitLogger

cognit_logger = CognitLogger()


class FuncStruct:
    def __init__(self, func_name, params=None):
        self.func_name = func_name
        self.params = params or []


class CExec(Executor):
    def __init__(self, fc: str, params: list[str]):
        self.fc = fc
        self.params_b64 = params
        self.params: list[Param]
        self.res: Optional[any]
        self.process_manager: Any
        # Function extraction attributes
        self.includes: list = []
        self.defines: list = []
        self.typedefs: list = []
        self.functions: list = []
        self.func_struct_list: list[FuncStruct] = []
        self.out_param_definition: list = []
        self.print_output_params: list = []
        self.func_calling: str = ""
        # Result
        self.result: Optional[any]
        # Execution times
        self.start_pyexec_time = 0.0
        self.end_pyexec_time = 0.1

    def raw_params_to_param_type(self):
        self.params = []
        for raw_param in self.params_b64:
            json_raw_param = json.loads(raw_param)
            # Only decode the IN params that have value
            if "value" in json_raw_param:
                decoded_value = base64.b64decode(json_raw_param["value"]).decode(
                    "utf-8"
                )
                json_raw_param["value"] = decoded_value
            param_instance = Param(**json_raw_param)
            self.params.append(param_instance)

    # Asuming receive string as something like:
    # with open('/content/sample_data/example.c', 'r') as file:
    # file_content = file.read()
    def extract_includes(self):
        lines = self.fc.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("#include"):
                self.includes.append(line)

    def extract_defines(self):
        lines = self.fc.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("#define"):
                self.defines.append(line)

    def extract_typedefs(self):
        lines = self.fc.split("\n")
        typedef = ""
        is_typedef = False

        for line in lines:
            line = line.strip()
            if line.startswith("typedef"):
                is_typedef = True
            if is_typedef:
                typedef += line
                if line.endswith(";"):
                    self.typedefs.append(typedef)
                    typedef = ""
                    is_typedef = False

    def extract_functions(self):
        lines = self.fc.split("\n")
        function = ""
        curly_bracket_count = 0
        continue_adding = 0

        for i in range(len(lines)):
            line = lines[i].strip()

            # Declaration needs the '{' at the end of the line or at the beginning of the next
            if line.startswith("void") and (
                (line.endswith("{") or ('{' in line and '}' in line)) #case bracket is in the same line
                or ((i + 1) < len(lines) and (lines[i + 1].strip().startswith("{"))) #case bracket is in the next line
            ):
                continue_adding = 1  # Once '{' is found, cotinue adding until curly_bracket_count == 0, that means end of func
                function += line
                curly_bracket_count += line.count("{") - line.count("}")
                # This case, func logic is declared in the same line as the declaration
                # CAUTION: if func is void sum(){ *c = a+b; and next line the } it will fail
                if curly_bracket_count == 0 and line.count("{") == 1:
                    continue_adding = 0
                # Add function calling and params
                self.extract_func_name_and_params(line)

            elif continue_adding == 1:
                function += line
                curly_bracket_count += line.count("{") - line.count("}")
                if curly_bracket_count == 0:
                    continue_adding = 0
            # print(f"Bracket: {curly_bracket_count}, Function: {function}, Continue: {continue_adding}")
            if curly_bracket_count == 0 and function != "" and continue_adding == 0:
                # print(f"Add {function}")
                cognit_logger.debug(f"Add {function}")
                self.functions.append(function)
                function = ""
                continue_adding = 0

        return self.functions

    def extract_func_name_and_params(self, line):
        line = line.strip()
        func_params = []

        # Validate that line starts with "void"
        if line.startswith("void "):
            # Delete "void" and spaces
            line = line[5:].lstrip()
            # Search for the first parenthesis index "("
            opening_parenthesis_index = line.find("(")
            # Get func name until first parenthesis index
            func_name = line[:opening_parenthesis_index].strip()
            # Get params from '(' until ')'
            params_str = line[opening_parenthesis_index + 1 : line.rfind(")")].strip()
            # Split params with ','
            params_list = [param.strip() for param in params_str.split(",")]

            if len(params_str.strip()) > 0:
                # Split params by commas
                params_list = [param.strip() for param in params_str.split(",")]
                # Process each param and add to list
                for param_str in params_list:
                    param_parts = param_str.strip().split(
                        " "
                    )  # [0] -> type, [1] -> var_name/ */ &, [2] -> var
                    param_type = param_parts[0]
                    param_name = next(
                        (part for part in param_parts[1:] if part.strip()), None
                    )
                    cognit_logger.debug(f"Param type: {param_type} Param name: {param_name}")
                    # Check if param is a pointer
                    if param_name.startswith("*") or param_type.endswith("*"):
                        if param_type.endswith("*"):
                            param_type = param_type[:-1]
                            cognit_logger.debug(f"Param type after edit: {param_type} Param name: {param_name}")
                        else:
                            # Delete spaces after *, if it's empty, var name is on param_parts[2]
                            param_name = param_parts[1][1:].lstrip()
                            if not param_name:
                                param_name = next(
                                    (part for part in param_parts[2:] if part.strip()), None
                                )
                        param_mode = "OUT"
                    else:
                        param_mode = "IN"
                    # Create a Param instance and add to the list
                    cognit_logger.debug(f"Param type: {param_type} Param name: {param_name} Param mode: {param_mode}")
                    param = Param(type=param_type, var_name=param_name, mode=param_mode)
                    func_params.append(param)
            else:
                cognit_logger.warning("There is no parametrers")
                param = Param(type="N/A", var_name="N/A", mode="N/A")
                func_params.append(param)

            # Create a FuncStruct instance and add to the list 'func_struct_list'
            func_struct = FuncStruct(func_name, func_params)
            self.func_struct_list.append(func_struct)
        else:
            cognit_logger.warning("Line doesn't start with void")

    def append_params_to_func_declaration(self, func_name):
        func_call = f"{func_name}("

        for i, param in enumerate(self.params):
            if param.mode == "IN":
                func_call += f"{param.value}"
            elif param.mode == "OUT":
                func_call += f"&{param.var_name}"

            if i < len(self.params) - 1:
                func_call += ","

        func_call += ");"

        return func_call

    def declare_output_param(self):
        for output_param_fc in self.func_struct_list:
            for output_param in output_param_fc.params:
                if output_param.mode == "OUT":
                    output_var_declaration = (
                        f"{output_param.type}" + " " + f"{output_param.var_name}" + ";"
                    )
                    self.out_param_definition.append(output_var_declaration)
                    self.print_output_params.append(output_param.var_name)

    def gen_func_call_with_params(self):
        for func_struct in self.func_struct_list:
            num_params = len(func_struct.params)
            matched_params = 0
            if num_params == len(self.params):
                for func_param, param_to_replace in zip(
                    func_struct.params, self.params
                ):
                    if (
                        (func_param.type == param_to_replace.type)
                        and (func_param.var_name == param_to_replace.var_name)
                        and (func_param.mode == param_to_replace.mode)
                    ):
                        cognit_logger.debug(
                            f"Param {param_to_replace} matches in function {func_struct.func_name}"
                        )
                        matched_params += 1

                        if matched_params == num_params:
                            cognit_logger.debug("All params matched")
                            func_calling = self.append_params_to_func_declaration(
                                func_struct.func_name
                            )

                            # print(func_calling)
                            cognit_logger.debug(f"Function generated: {func_calling}")
                            return func_calling
                        else:
                            cognit_logger.warning("Not all params matched")
                    else:
                        cognit_logger.warning(
                            f"Param {func_param.var_name} doent match func {func_struct.func_name}"
                        )
            else:
                cognit_logger.error(
                    "Number of params requested =! number of func params"
                )

    def run(self):
        try:
            cognit_logger.info("Starting C function execution task")
            self.start_pyexec_time = time.time()
            self.raw_params_to_param_type()
            clingArgs = []
            clingPath = os.path.expanduser(
                "~/cling_git/cling_2020-11-05_ROOT-ubuntu18.04/bin/cling"
            )
            self.extract_includes()
            self.extract_defines()
            self.extract_typedefs()
            self.extract_functions()
            self.declare_output_param()
            self.func_calling = self.gen_func_call_with_params()

            # clingArgs.append(".rawInput")
            # Add includes
            if len(self.includes) != 0:
                for include in self.includes:
                    clingArgs.append(include)
            # Add defines definitios
            if len(self.defines) != 0:
                for define in self.defines:
                    clingArgs.append(define)
            # Add typedefs definitios
            if len(self.typedefs) != 0:
                for typedef in self.typedefs:
                    clingArgs.append(typedef)
            # Add func definitios
            if len(self.functions) != 0:
                for function in self.functions:
                    clingArgs.append(function)
            # Add output param definition
            if len(self.out_param_definition) != 0:
                for output_param in self.out_param_definition:
                    clingArgs.append(output_param)
            # Add function calling, need to add None check in case none func matches
            if self.func_calling != None and len(self.func_calling.strip()) != 0:
                clingArgs.append(self.func_calling)

            # Adds output var name to get the output
            if len(self.print_output_params) != 0:
                for output_param_to_print in self.print_output_params:
                    clingArgs.append(output_param_to_print)

            cognit_logger.debug(f"clingArgs: {clingArgs}")

            # Cling doesn't accept the code as clingArgs due to \n. Need to be something like:
            # "#include <stdio.h>" + '\n' + "void sum(int a, int b, float *c){*c = a + b;}" +'\n'+ "float c;" '\n' + "sum(3, 4, &c);" + '\n'+ "c"
            cling_code = ""
            for line in clingArgs:
                cling_code += str(line)
                cling_code += "\n"

            cognit_logger.debug(f"cling_code: {cling_code}")

            process = subprocess.Popen(
                [clingPath], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
            )
            output, error = process.communicate(input=cling_code)

            listResult = output.split()
            # Parse the output as the output type
            for i, param in enumerate(self.params):
                if param.mode == "OUT":
                    if param.type == "float":
                        float_value_in_str = listResult[-1].rstrip("f")  # Deletes 'f' sufix
                        self.result = float(float_value_in_str)
                    elif param.type == "int":
                        self.result = int(listResult[-1])
                    elif param.type == "str":
                        self.result = str(listResult[-1])
                    elif param.type == "bool":
                        self.result = bool(listResult[-1])
                    else:
                        self.result = listResult[-1]

            cognit_logger.info(f"Run C fuction: {self.fc}")
            cognit_logger.info(f"Result: {self.result}")
            self.end_pyexec_time = time.time()
            return
        except Exception as e:
            cognit_logger.error(f"Error while running C function: {e}")
            self.res = None
            self.end_pyexec_time = time.time()
            raise HTTPException(status_code=400, detail="Error executing function")
        return

    def get_result(self):
        cognit_logger.debug("Get C result func")
        cognit_logger.info(f"Result: {self.result}")
        return self.result
