# inbound-feeds-poc

## Installation

Create a virtual environment, activate it and install the adapter requirements.

``$ pip3 install -r requirements.txt``

Set up the environment variables in the .env file.  Copy and rename `.env.example` to `.env.`  Fill in the variable values.

``$ cp .env.example .env``

Run tests to see all pass and verify successfull installation.

``$ pytest ``


## Pycharm Configuration and Debugging

Using the Pycharm IDE you can run this code locally and will have the ability to inspect its methods and processes.

Once the repo is installed locally and the virtual environment is created -- lets assume the virtual env is named `inbound-feeds-poc` -- open the location of the repo in Pycharm as a project

``Pycharm menu > File > Open > {navigate to repository root} > Open > {choose to open in new window}``

Create a Pycharm configuration and point it to the virtual environment that has already been set up.
Pycharm menu > Pycharm > Preferences > Project: inbound-feeds-poc > Python Interpreter

If the virtual environment is not already listed in the drop down, 

- select the gear icon
- select Add...
- in the window that opens, select Existing Environment
- select ... icon at the end of the interpreter drop down
- in the window that opens, navigate to the location of the virtual environment folder
- in the virtual environment folder look for the python bin file, likely in `/environment/bin` folder
- save your changes to complete

Pycharm will take some time to rebuild its indexes.  With the Interpreter set up you can create a debugging configuration.  Once set up you can run this configuration which will start up a locally running Flask server.  From this server you can run the adapter locally and if you set debugging breakpoints, interrupt the flow of control and inspect the process in action.

With the repository open in Pcharm, locate the drop down across the top of the window where you see the first option within, "Edit Configurations".

- open the Edit Configurations window
- select the plus (+) icon
- select Python from menu
- set Script Path to `/inbound-feeds-poc/apps/associated_press/__init__.py`
- set Working Directory to `/inbound-feeds-poc/apps/associated_press/`
- verify that the Python Interpreter has been automatically set to the correct value
- save your changes to complete

Now either the green arrow icon or the green bug icon next to the configurations drop down will launch and run the POC.

## Run application from terminal

If you do not want to run the app from a Pycharm cofiguration, run it with the terminal.

``$ PYTHONPATH=.  python apps/associated_press/__init__.py ``

An example of the log file generated at this endpoint is in the fixtures directory `apps_associated_press_init_main_log.json`

Run the app api endpoint.

`` ... fill this in ... ``
