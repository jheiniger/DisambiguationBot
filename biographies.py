import aiohttp
import asyncio
from collections import namedtuple
import numpy as np
import pywikiapi
import re
import sys

import reader


# Regexps biographies

regexp_birth = re.compile(r"^\*\s*(\d+)[-\d\.]*\s*\/.*?Naissance.+$", re.MULTILINE)
regexp_death = re.compile(r"^\*\s*(\d+)[-\d\.]*\s*\/.*?Décès.+$", re.MULTILINE)

regexp_election = re.compile(r"^\*.*[EÉ]lection.*?(?:en tant que|comme|au poste de) ([\w '-]+).*$", re.MULTILINE)
regexp_nomination = re.compile(r"^\*.*Nomination.*?(?:comme|au titre de) ?((?:(?! par)[\w '-])+).*$", re.MULTILINE)

regexp_wikidata = re.compile(r"^Wikidata: (Q\d+).*$", re.MULTILINE)

# Regexps bottin

regexp_BotBottin2_3_4 = re.compile(r"^\*.*Mention de.*?(?:dans la catégorie|avec la catégorie) ([\w '-]+).*$", re.MULTILINE)
regexp_BotBottin1_5 = re.compile(r"^\*.* est mentionné dans la catégorie ([\w '-]+).*$", re.MULTILINE)
regexp_BotBottin6 = re.compile(r"^\*.*([\w '-]+), exerce son activité au .*$", re.MULTILINE)

# Utility for getting matching groups directly.
def regexp_match(regexp, text):
  match = regexp.search(text)

  if match:
    return match.groups()[0]


# Wikipast

site_wikipast = pywikiapi.Site("http://wikipast.epfl.ch/wikipast/api.php")
site_wikipast.no_ssl = True

def edit_page(title, text):
  site_wikipast('edit', title=title, text=text, token=site_wikipast.token())


# Wikidata

async def get_wikidata_description(wikidata_id, *, session):
  async with session.get(f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={wikidata_id}&format=json&formatversion=2") as resp:
    if resp.status == 429:
      print(f"Warning: Wikidata returned HTTP 429", file=sys.stderr)
      return None

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
  page = reader.get_page(name)

  if not page:
    return None

  text = reader.wikidata_to_text(page['wikitext'])

  birth = regexp_match(regexp_birth, text)
  death = regexp_match(regexp_death, text)

  jobs = re.findall(regexp_nomination, text)
  wikidata_id = regexp_match(regexp_wikidata, text)

  if wikidata_id:
    if not wikidata_id in wikidata_cache:
      wikidata_cache[wikidata_id] = await get_wikidata_description(wikidata_id, session=session)

    description = wikidata_cache[wikidata_id]
    if description: jobs.append(description)

  if birth or death or jobs:
    return Person(birth=birth, death=death, job=jobs[-1] if jobs else None, name=name)
  
  # Bottin part
  
  job_BotBottin2_3_4 = regexp_match(regexp_BotBottin2_3_4, text)  

  if job_BotBottin2_3_4:
    return Person(birth=None, death=None, job=job_BotBottin2_3_4, name=name)

  job_BotBottin1_5 = regexp_match(regexp_BotBottin5, text)
    
  if job_BotBottin1_5:
    return Person(birth=None, death=None, job=job_BotBottin1_5, name=name)

  job_BotBottin6 = regexp_match(regexp_BotBottin6, text)
    
  if job_BotBottin6:
    return Person(birth=None, death=None, job=job_BotBottin6, name=name)

  # Return None is there is no sign that the page represents a person.
  return None


# Storage

Homonyms = namedtuple("Homonyms", ["name", "people"])
homonyms_names = np.load("name_homonomys.npy", allow_pickle=True)[0:1000]
disambiguation_names = np.load("disambiguation_names.npy", allow_pickle=True)


async def create_list():
  # Limit to 30 parallel connections to avoid HTTP 429 "Too many requests" responses from Wikidata.
  session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=30))
  homonyms_list = list()
  done = 0

  async def process_homonyms(index):
    nonlocal done

    homonyms = homonyms_names[index]
    wikidata_cache = dict() # The cache is per group of homonyms.

    people = [page for page in await asyncio.gather(*[find_page(name, session=session, wikidata_cache=wikidata_cache) for name in homonyms[0:-1]]) if page is not None]

    # Only load the last entry if there is more than one person found already.
    if len(people) >= 1:
      page = await find_page(homonyms[-1], session=session, wikidata_cache=wikidata_cache)
      if page: people.append(page)

    if len(people) > 1:
      homonyms_list.append(Homonyms(name=disambiguation_names[index].title(), people=people))

    done += 1
    print(f"\r{done}/{len(homonyms_names)}", end="", file=sys.stderr)


  await asyncio.gather(*[process_homonyms(index) for index in range(len(homonyms_names))])
  await session.close()

  return homonyms_list


# Formatting

def format_homonyms(homonyms):
  output = str()
  output += f"[[{homonyms.name} (disambiguation)|{homonyms.name}]] peut désigner :\n"

  for person in homonyms.people:
    output += f"* [[{person.name}]]"

    if person.birth:
      output += f" ({person.birth}\xa0– {person.death or str()})"

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
