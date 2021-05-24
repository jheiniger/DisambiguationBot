import aiohttp


common = { 'format': "json", 'formatversion': "2" }

class Writer:
  def __init__(self, *, username, password, overwrite):
    self._origin = "http://wikipast.epfl.ch/w/api.php"

    self._username = username
    self._password = password
    self._overwrite = overwrite

    self._csrf = None
    self._session = None

  async def close(self):
    await self._session.close()

  async def open(self):
    self._session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=30))

    result_token = await self._fetch({ 'action': "query", 'meta': "tokens", 'type': "login" })
    token = result_token['query']['tokens']['logintoken']

    result_login = await self._fetch({ 'action': "login", 'lgname': self._username, 'lgpassword': self._password, 'lgtoken': token })

    if result_login['login']['result'] == "Failed":
      raise Exception(result_login['login']['reason'])

    result_csrf = await self._fetch({ 'action': "query", 'meta': "tokens", 'type': "csrf" })
    self._csrf = result_csrf['query']['tokens']['csrftoken']

  async def write(self, title, text):
    result_edit = await self._fetch({ 'action': "edit", 'bot': True, 'title': title, 'text': text, 'token': self._csrf, **({ 'createonly': True } if not self._overwrite else {}) })

    if result_edit['edit']['result'] != "Success":
      raise Exception("A problem occured")

  async def _fetch(self, data):
    async with self._session.post(self._origin, data={ **common, **data }) as resp:
      result = await resp.json()

      if 'error' in result:
        raise Exception(result['error']['info'])

      return result
