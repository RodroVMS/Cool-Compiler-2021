import os
from os import path
from pipeline import Pipeline
from grammar import G

first = 0
total_test = 10
directory = "./cool_scripts_auto/"

pipe = Pipeline(G)
files = sorted([file for file in os.listdir(directory)])
print(files)
for i in range(first, min(len(files, total_test))):
    file = files[i]
    _file = path.join(directory, file)
    text =  ''.join(line for line in open(_file, 'r', encoding='utf8'))
    try:
        print(pipe(text))
        print("End of exucution of file", file)
    except KeyboardInterrupt:
        print("Interrupt of",file)
    input()