import aiohttp
import asyncio
from bs4 import BeautifulSoup
from collections import namedtuple
import pywikiapi
import re
import sys

from pprint import pprint


# Regexps

regexp_birth = re.compile(r"^(\d+)[-\d\.]*\s*\/.*?Naissance.+$")
regexp_death = re.compile(r"^(\d+)[-\d\.]*\s*\/.*?Décès.+$")

regexp_election = re.compile(r"^.*[EÉ]lection.*?(?:en tant que|comme|au poste de) ([\w '-]+).*$")
regexp_nomination = re.compile(r"^.*Nomination.*?(?:comme|au titre de) ?((?:(?! par)[\w '-])+).*$")

regexp_wikidata = re.compile(r"^Wikidata: (Q\d+).*$")

# Utility for getting matching groups directly.
def regexp_match(regexp, text):
  match = regexp.match(text)

  if match:
    return match.groups()[0]


# Wikipast

site_wikipast = pywikiapi.Site("http://wikipast.epfl.ch/wikipast/api.php")
site_wikipast.no_ssl = True

async def get_page(title, *, session):
  async with session.get(f"http://wikipast.epfl.ch/wikipast/api.php?action=parse&page={title}&format=json&formatversion=2") as resp:
    if resp.status == 500:
      # print(await resp.text())
      print(f"Warning: Server returned HTTP 500 for '{title}'", file=sys.stderr)
      return None

    data = await resp.json()

    if 'error' in data:
      print(f"Warning: Request error for '{title}'", file=sys.stderr)
      return None

    return BeautifulSoup(data['parse']['text'], "html.parser")

def edit_page(title, text):
  site_wikipast('edit', title=title, text=text, token=site_wikipast.token())


# Wikidata

async def get_wikidata_description(wikidata_id, *, session):
  async with session.get(f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={wikidata_id}&format=json&formatversion=2") as resp:
    data = await resp.json()
    entity = data['entities'].get(wikidata_id)

    if entity:
      descriptions = entity.get('descriptions')
      if not descriptions: return None

      desc = descriptions.get('fr') or descriptions.get('en')

      if desc: return desc['value']

  return None

# ---

Person = namedtuple("Person", ["birth", "death", "job", "name"])

async def find_page(name, *, session, wikidata_cache):
  page = await get_page(name, session=session)

  if not page:
    return None

  birth = None
  death = None
  jobs = list()

  # Search for birth, death, nomination and election keywords.
  for ul in page.select("ul"):
    for li in ul.select("li"):
      text = li.get_text()

      if birth is None:
        match_birth = regexp_match(regexp_birth, text)
        if match_birth: birth = match_birth

      if death is None:
        match_death = regexp_match(regexp_death, text)
        if match_death: death = match_death

      match_nomination = regexp_match(regexp_nomination, text)
      if match_nomination: jobs.append(match_nomination)

      match_election = regexp_match(regexp_election, text)
      if match_election: jobs.append(match_election)

  # Search for the wikidata id.
  wikidata_id = None

  for p in page.select("p"):
    text = p.get_text()

    if wikidata_id is None:
      wikidata_id = regexp_match(regexp_wikidata, text)

  if wikidata_id:
    if not wikidata_id in wikidata_cache:
      wikidata_cache[wikidata_id] = await get_wikidata_description(wikidata_id, session=session)

    description = wikidata_cache[wikidata_id]
    if description: jobs.append(description)

  if birth or death or jobs:
    return Person(birth=birth, death=death, job=jobs[-1] if jobs else None, name=name)

  # Return None is there is no sign that the page represents a person.
  return None


# Storage

Homonyms = namedtuple("Homonyms", ["name", "people"])

def save_list(homonyms_list, filename):
  serialized = [[homonyms.name, [list(person) for person in homonyms.people]] for homonyms in homonyms_list]
  json.dump(serialized, open(filename, "w"))

def load_list(filename):
  serialized = json.load(open(filename))
  return [Homonyms(name=homonyms[0], people=[Person(*person) for person in homonyms[1]]) for homonyms in serialized]


# Loop

import json
import numpy as np

homonyms_names = np.load("name_homonomys.npy", allow_pickle=True)[0:1000]

async def create_list():
  session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=200))
  homonyms_list = list()
  done = 0

  async def process_homonyms(index):
    nonlocal done

    homonyms = homonyms_names[index]
    wikidata_cache = dict()
    people = [page for page in await asyncio.gather(*[find_page(name, session=session, wikidata_cache=wikidata_cache) for name in homonyms]) if page is not None]

    if len(people) > 1:
      homonyms_list.append(Homonyms(name="Someone", people=people))

    done += 1
    print(f"\r{done}/{len(homonyms_names)}", end="", file=sys.stderr)
    # pprint(people)

  await asyncio.gather(*[process_homonyms(index) for index in range(len(homonyms_names))])
  await session.close()

  return homonyms_list


# save_list(homonyms_list, "0-1000.json")
# homonyms_list = load_list("0-1000.json")


# Formatting

def format_homonyms(homonyms):
  output = str()
  output += f"[[{homonyms.name}]] peut désigner :\n"

  for person in homonyms.people:
    output += f"* [[{person.name}]]"

    if person.birth:
      output += f" ({person.birth} – {person.death or str()})"

    if person.job:
      output += f", {person.job}"

    output += "\n"

  return output


# Main

async def main():
  homonyms_list = await create_list()

  for homonyms in homonyms_list:
    print(format_homonyms(homonyms))


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
