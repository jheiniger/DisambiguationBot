# DisambiguationBot

## Usage

```
$ pip3 install -r requirements.txt
$ curl -L https://github.com/dhlab-epfl/HUM-369-tutorials/releases/download/2.0/all_data_20210407.json.gz | gunzip > dump.json
$ python3 build.py # can take a few minutes
$ python3 biographies.py # to list pages
$ python3 biographies.py --username <username> --password <password> # to write pages
# Additional options:
#   --overwrite: Overwrite exising pages (otherwise an error is thrown)
#   --range: Act on a subset of groups, with the same slice syntax as Python (e.g. 500:600 -> groups 500 to 600)
```
