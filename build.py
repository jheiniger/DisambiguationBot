import json


input = open("dump.json", "r")
data = json.load(input)

print("Loaded")


data = sorted(data, key=lambda item: item['title'] if ('title' in item) else 'a')

print("Sorted")


output = open("dump.dat", "w")
output_offsets = open("dump_offsets.json", "w")

ignored = 0
offset = 0
offsets = []

for item in data:
  if 'title' in item:
    # json.dumps(item['title']) + "\t" +
    line = json.dumps(item) + "\n"
    output.write(line)

    offsets.append(offset)
    offset += len(line)
  else:
    ignored += 1

json.dump(offsets, output_offsets)

print("Done")
print(f"Ignored {ignored} pages")
