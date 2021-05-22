import json
import re


file = open("dump.dat", "r")

index = 0
data = list()

line_offsets = json.load(open("dump_offsets.json", "r"))
line_cache = dict()

def get_index(index, *, storecache = False):
  if index in line_cache:
    return line_cache[index]

  file.seek(line_offsets[index])
  data = json.loads(file.readline())

  if storecache:
    line_cache[index] = data

  return data


def get_page(title):
  def binary_search(a_index, b_index, a_value = None, b_value = None, depth = 0):
    if a_value is None: a_value = get_index(a_index, storecache=True)['title']
    if b_value is None: b_value = get_index(b_index, storecache=True)['title']

    mid_index = int((a_index + b_index) * 0.5)

    if a_index == mid_index:
      return None

    mid_obj = get_index(mid_index, storecache=depth < 10)
    mid_value = mid_obj['title']

    if mid_value > title:
      return binary_search(a_index, mid_index, a_value, mid_value, depth + 1)
    elif mid_value < title:
      return binary_search(mid_index, b_index, mid_value, b_value, depth + 1)
    else:
      return mid_obj

  return binary_search(0, len(line_offsets) - 1)


# Order is important here.
substitutions = [
  (r"{(?:.|\n)*?}", ""),

  (r"\[\[(?:[^\]]*\|)?(.*?)]]", r"\1"),
  (r"\[.*?(?: (.*?))?]", r"\1"),

  (r"'''(.*?)'''", r"\1"),
  (r"''(.*?)''", r"\1")
]

def wikidata_to_text(text):
  for pattern, repl in substitutions:
    text = re.sub(pattern, repl, text)

  return text


if __name__ == '__main__':
  for name in ["Bob Dylan", "Emile Zola", "Marie Feodorovna", "Pablo Picasso"]:
    print(name, get_page(name))
    print()
