from modules._logger import CognitLogger
from modules._executor import *
from models.faas import *

from typing import Any, Optional
import subprocess
import base64
import time
import json
import os

cognit_logger = CognitLogger()

class FuncStruct:

    def __init__(self, func_name, params=None):

        self.func_name = func_name
        self.params = params or []

class CExec(Executor):

    def __init__(self, fc: str, params: list[str]):

        self.lang = "C"
        self.fc = fc
        self.params_b64 = params
        self.params: list[Param]
        self.process_manager: Any

        # Function extraction attributes
        self.includes: list = []
        self.defines: list = []
        self.typedefs: list = []
        self.functions: list = []
        self.func_struct_list: list[str] = []
        self.func_name_2_exec: str = ""
        self.param_definition_list: list = []
        self.print_output_params: list = []
        self.func_calling: str = ""

        # Result
        self.res: Optional[any]
        # Execution times
        self.start_pyexec_time = 0.0
        self.end_pyexec_time = 0.1
        self.process: subprocess.Popen

    def raw_params_to_param_type(self):
        self.params = []
        for raw_param in self.params_b64:
            json_raw_param = json.loads(raw_param)
            # Only decode the IN params that have value
            if "value" in json_raw_param and json_raw_param["mode"] == "IN":
                decoded_value = base64.b64decode(json_raw_param["value"]).decode(
                    "utf-8"
                )
                json_raw_param["value"] = decoded_value
            param_instance = Param(**json_raw_param)
            self.params.append(param_instance)

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
                self.extract_func_name(line)

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

    def extract_func_name(self, line):
        line = line.strip()

        # Validate that line starts with "void"
        if line.startswith("void "):
            # Delete "void" and spaces
            line = line[5:].lstrip()
            # Search for the first parenthesis index "("
            opening_parenthesis_index = line.find("(")
            # Get func name until first parenthesis index
            func_name = line[:opening_parenthesis_index].strip()
            # Add func name to list
            self.func_name_2_exec = func_name
        else:
            cognit_logger.warning("Line doesn't start with void")

    def declare_all_params(self):
        for param in self.params:
            if param.mode == "OUT":
                param_declaration = (
                    f"{param.type}" + " " + f"{param.var_name}" + ";"
                )
                self.print_output_params.append(param.var_name) # Print output param for getting the value in stdout
            elif param.mode == "IN":
                if param.type == "char":
                    param_declaration = (
                        f"{param.type}" + " " + f"{param.var_name}" + "[] = " + f'"{param.value}"' + ";"
                    )
                else: # Case int, float, bool
                    param_declaration = (
                        f"{param.type}" + " " + f"{param.var_name}" + " = " + f"{param.value}" + ";"
                    )
            self.param_definition_list.append(param_declaration)

    def append_params_to_func_declaration(self, func_name):
        func_call = f"{func_name}("

        for i, param in enumerate(self.params):
            if param.mode == "IN":
                func_call += f"{param.var_name}"
            elif param.mode == "OUT":
                func_call += f"&{param.var_name}"

            if i < len(self.params) - 1:
                func_call += ","

        func_call += ");"

        return func_call

    def run(self):
        try:
            cognit_logger.info("Starting C function execution task")
            self.start_pyexec_time = time.time()
            self.raw_params_to_param_type()
            clingArgs = []
            clingPath = os.path.expanduser(
                "/root/cling_test/cling_2020-11-05_ROOT-ubuntu18.04/bin/cling"
            )

            self.extract_includes()
            self.extract_defines()
            self.extract_typedefs()
            self.extract_functions()
            self.declare_all_params()
            self.func_calling = self.append_params_to_func_declaration(self.func_name_2_exec)

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
            if len(self.param_definition_list) != 0:
                for output_param in self.param_definition_list:
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

            self.process = subprocess.Popen(
                [clingPath], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
            )
            output, error = self.process.communicate(input=cling_code)

            listResult = output.split()

            # Parse the output as the output type
            for i, param in enumerate(self.params):

                if param.mode == "OUT":
                    if param.type == "float":
                        float_value_in_str = listResult[-1].rstrip("f")  # Deletes 'f' sufix
                        self.res = float(float_value_in_str)
                    elif param.type == "int":
                        self.res = int(listResult[-1])
                    elif param.type == "str":
                        self.res = str(listResult[-1])
                    elif param.type == "bool":
                        self.res = bool(listResult[-1])
                    else:
                        self.res = listResult[-1]

            cognit_logger.info(f"Run C fuction: {self.fc}")
            cognit_logger.info(f"Result: {self.res}")
            self.end_pyexec_time = time.time()
            return self
        
        except Exception as e:

            cognit_logger.error(f"Error while running C function: {e}")
            self.res = None
            self.end_pyexec_time = time.time()
            self.err = "Error executing C function: " + str(e)
            self.ret_code = ExecReturnCode.ERROR

    def get_result(self):

        cognit_logger.debug("Get C result func")
        cognit_logger.info(f"Result: {self.res}")
        return self.res
