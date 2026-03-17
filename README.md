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

The wire service this POC pulls from is the **Associated Press**.  In order to run the POC you will need access to a valid AP API token. You will also need an Arc XP provisioned organization and access to Arc XP's Composer, Photo Center and Site Service applications.

Note: AP feed requests in this POC send the API key using the `x-api-key` request header (per AP Media API docs), sourced from `AP_API_KEY` in your `.env`.

For **image downloads**, the Associated Press API also expects the API key in the request headers when fetching the binary image. Migration Center and Photo Center, however, do not forward arbitrary headers when they later dereference the original AP image URL. As a result, this POC cannot directly import AP photos into Arc XP via their original AP URLs when going through Migration Center or Photo Center.

To ingest photos in a production-ready design, you would typically introduce another layer that:

- Performs an authenticated HTTP GET to AP to download the image (including the `x-api-key` header).
- Stores the binary in a location you control (for example, a public or pre-signed S3 URL).
- Updates the photo ANS `originalUrl` (or equivalent field) to point at that new URL before sending it to Migration Center or Photo Center.
- Runs a separate clean‑up process to remove images from that storage once you have verified they have successfully imported into Photo Center.

## Ingestion flow (high level)

- Wire content is fetched from the Associated Press feed.
- The wire items are transformed into Arc XP **ANS** objects using the converters in `apps/associated_press/converter.py`.
- The resulting ANS is sent to **Arc XP Migration Center API** rather than directly to the Draft or Photo APIs.
  - **Stories** are wrapped in a Migration Center payload of the form:

    ```json
    {
      "ANS": { ... },
      "circulations": [ { ... } ],
      "operations": [ { "type": "story_operation", "operation": "delete", "organization_id": "<org>", ... } ]
    }
    ```

  - **Photos** are wrapped as:

    ```json
    {
      "ANS": { ... }
    }
    ```

- Migration Center then routes the content into the appropriate Arc XP services.

## Installation

> WARNING: This is a proof-of-concept application. Do not use it in a production deployment. Develop a production application instead.

Create a virtual environment, activate it and install the adapter requirements.

Example with Python 3.10 and `mkvirtualenv`:

```shell
mkvirtualenv -p $(which python3.10) inbound-feeds-poc
pip install -r requirements.txt
```

Set up the application's environment variables in a .env file.  To create a .env with fill-in-the-blank named variables, copy and rename `.env.example` from the repo to `.env.`

``$ cp .env.example .env``

Run tests to see all pass and verify successful installation.

```shell
pytest
```


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

## Example log output

Running the ingest script directly:

```shell
PYTHONPATH=. python apps/associated_press/__init__.py
```

will produce structured JSON log lines similar to the example fixture in `tests/fixtures/apps_associated_press_init_main_log.json`. For example:

```text
{"message": "200 https://api.ap.org/media/v/content/feed", "previous_sequence": null, "sequence": "19583896609233", "next_page": "https://api.ap.org/media/v/content/feed?qt=3dHoqmJl29eF&seq=19583896609233"}
{"message": "Unprocessable wire type: video"}
{"message": "Picture excluded because it would incur cost", "source_id": "82fc21768c8147fd94973f3823a9bf01", "priced": true, "pricetag": "USD:35.00"}
{"message": "SQLite3 connection created 2.6.0 to db :memory:"}
{"message": "1 of 2 <apps.associated_press.converter.APStoryConverter object ...>"}
{"message": "GENERATE ANS & CIRCULATION & OPERATION"}
{"message": "text source data", "source_id": "c2d69c69b1c16d147d0ea4b46d8fd784", "headline": "rolv LLC Launches rolvsparse©: A New Mathematical Operator That Makes Every Computer on Earth Run AI Faster -- With 99% Less Energy", "firstcreated": "2026-03-17T15:35:00Z", ...}
{"message": "text conversion", "arc_id": "5OMU2X3T7QV7EFDK5MEVDL47UA", "source_id": "c2d69c69b1c16d147d0ea4b46d8fd784", "headline": "rolv LLC Launches rolvsparse©: A New Mathematical Operator That Makes Every Computer on Earth Run AI Faster -- With 99% Less Energy", ...}
{"message": "story circulation", "arc_id": "5OMU2X3T7QV7EFDK5MEVDL47UA", ...}
{"message": "story delete operation", "scheduled_delete": {"type": "story_operation", "operation": "delete", "date": "2026-03-20T00:00:00Z", "organization_id": "sandbox.cetest", ...}}
{"message": "CHECK INVENTORY - DOES SAME SHA1 EXIST?"}
{"message": "SEND STORY TO MIGRATION CENTER API"}
{"message": "SAVE INVENTORY"}
{"message": "2 of 2 <apps.associated_press.converter.APPhotoConverter object ...>"}
{"message": "GENERATE ANS"}
{"message": "picture source data", "source_id": "ed7a982594414a578e0f978a5f8ab962", "headline": "Britain Ukraine NATO", ...}
{"message": "photo conversion", "arc_id": "7UVFD743QED755B3AUE7FK3VVY", "source_id": "ed7a982594414a578e0f978a5f8ab962", ...}
{"message": "SEND PHOTO TO MIGRATION CENTER API"}
{"message": "AP APIKEY REQUEST HEADERS CANNOT BE ADDED TO MC or PC API, MISSING WHEN PHOTO CENTER ATTEMPTS AP DOWNLOAD, AP PHOTO NOT IMPORTED TO ARC XP"}
{"message": "SAVE INVENTORY"}
```

The full sample log can be viewed in `tests/fixtures/apps_associated_press_init_main_log.json` and is useful for understanding the end‑to‑end behavior of the ingest run (feed fetching, filtering, conversion, Migration Center calls, and inventory updates).
