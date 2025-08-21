# inbound-feeds-poc

**_inbound-feeds-poc_** is a proof of concept application, developed as a demonstration of pulling wire content, transforming the wire content into ANS format, then sending the transformed ANS into Arc. Read on ALC about the process of pulling external content into Arc via building an [Inbound Feeds Adapter](https://docs.arcxp.com/en/products/publishing-platform/how-to-ingest-wire-content-using-an-inbound-wires-adapter.html).

This POC is not designed for use in a production environment.  It is provided as a simple example of the general concepts and suggestions described in the ALC article:

- connecting to the associated press feed
- pulling wire content out of the feed
- transforming wire content into ans
- creating a hash value from the wire content
- sending converted ans into arc
- logging transformation, errors and successes
- adding to an inventory database
- some unit tests

This application does not model scheduling itself to run repeatedly on a timed cycle.

The wire service this POC pulls from is the Associated Press.  In order to run the POC you will need access to a valid AP API token. You will also need an Arc provisioned organization and access to Arc's Composer, Photo Center and Site Service applications.

## Installation

> WARNING: This is a proof-of-concept application. Do not use it in a production deployment. Develop a production application instead.

Create a virtual environment, activate it and install the adapter requirements.

``$ pip3 install -r requirements.txt``

Set up the application's environment variables in a .env file.  To create a .env with fill-in-the-blank named variables, copy and rename `.env.example` from the repo to `.env.`

``$ cp .env.example .env``

Run tests to see all pass and verify successful installation.

``$ pytest ``


## Pycharm Configuration and Debugging

Using the PyCharm IDE you can run this code locally and will have the ability to inspect its methods and processes.

Once the repo is installed locally and the virtual environment is created -- lets assume the virtual env is named `inbound-feeds-poc` -- open the location of the repo in Pycharm as a project.

``Pycharm menu > File > Open > {navigate to repository root} > click Open button > {choose to open repository project in new window}``

Create a PyCharm configuration and point it to the virtual environment that has already been set up.

```Pycharm menu > PyCharm > Preferences > Project: inbound-feeds-poc > Python Interpreter```

If the virtual environment is not already listed in the drop down: 

- select the gear icon
- select "Add..."
- in the window that opens, select "Existing Environment"
- select "..." icon at the end of the interpreter drop down
- in the window that opens, navigate to the location of the virtual environment folder
- in the virtual environment folder look for the python bin file, likely in `/environment/bin` folder
- save your changes to complete

PyCharm will take some time to rebuild its indexes.  With the Interpreter set up you can create a debugging configuration.  Once set up, you can run this configuration which will start up a locally running Flask server.  From this server you can run the adapter locally and if you set debugging breakpoints, interrupt the flow of control and inspect the application in action.

With the repository open in PyCharm, locate the drop down across the top of the window. This drop down may appear empty, but if you select it you will se there is an option within, "Edit Configurations".

- select "Edit Configurations" from the drop down, opening the Edit Configurations window
- select the plus (+) icon
- select Python from menu
- set Script Path to `/inbound-feeds-poc/apps/associated_press/__init__.py`
- set Working Directory to `/inbound-feeds-poc/apps/associated_press/`
- verify that the Python Interpreter has been automatically set to the correct value
- save your changes to complete

Now either the green arrow icon or the green bug icon next to the configurations drop down will launch and run the POC.

## Run POC from terminal

You may run the application directly from the terminal.

``$ PYTHONPATH=.  python apps/associated_press/__init__.py ``

An example of the log file generated at this endpoint is in the fixtures directory `/inbound-feeds-poc/tests/fixtures/apps_associated_press_init_main_log.json`

Or you can run the api endpoint. 

`` $ PYTHONPATH=. python api/associated_press.py ``

Once the api is running in the terminal, open an api browser and navigate to the localhost api url `http://127.0.0.1:8080/api/ap/`

## Errata

Other terminal commands
```shell
$ isort . # reorders and formats imports
$ black . # reformats code, including imports

```

Terminal logs will pause when the rate limits enforced by the `@limits()` and `@sleep_and_retry` decorators are hit.  After a couple of minutes, the logs will unpause and pick back up where they left off until the rate limits run out again, causing another pause, or the script finishes.
