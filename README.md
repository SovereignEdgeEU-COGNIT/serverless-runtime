# Serverless runtime
This repository holds the python implementation of the Serverless Runtime. The Serverless Runtime is the service deployed into the scheduled node that will be in charge to execute the offloaded tasks. This service exposes the Serverless Runtime API to allow the devices to upload the functions and the needed data to execute them.

## Set up
Python v3.10.6

For setting it up it is recommended installing the module virtualenv or, in order to keep the dependencies isolated from the system. 

```
pip install virtualenv
```
After that, one needs create a virtual environment and activate it:

```
python -m venv serverless-env
source serverless-env/bin/activate
```
The following installs the needed dependencies from the requirements.txt file:
```
pip install -r requirements.txt
```

## User's manual
### Quick run of Serverless runtime

The application is built on top of FastAPI framework,.
In order to quickly run a serverless runtime instance a user can make use of the uvicorn tool:
```
cd app/
uvicorn main:app --host 0.0.0.0 --port 8000
```
```log
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [411] using StatReload
INFO:     Started server process [413]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

For a detailed description of the API's endpoint features access:

```
http://0.0.0.0:8000/docs/
 ```


### Tests
The test are found in the `test/` folder. The tests are written using the pytest framework. In order to run the tests, the following command can be used:

```
cd app/test/
pytest --log-cli-level=DEBUG -s
```

To run unit tests:

```
pytest --log-cli-level=DEBUG -s test_faas.py
pytest --log-cli-level=DEBUG -s test_cexec.py
pytest --log-cli-level=DEBUG -s test_pyexec.py
```

A README document is available in `docs/`, explaining how to test synchronous and asynchronous execution calls.   
