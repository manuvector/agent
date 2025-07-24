import os
import sys
ignore = ['node_modules']
extension=[]
if len(sys.argv)>2:
    extension= (sys.argv[2])
if len(extension)<1:
    extension = ('.py', '.html', '.js', '.css')

for root, dirs, files in os.walk(sys.argv[1]):
    for file in files:
        if file.endswith(extension):
            filepath = os.path.join(root, file)
            if any([f in filepath for f in ignore]):
                continue
            print(f'File: {filepath}')
            with open(filepath, 'r', encoding='utf-8') as f:
                print(f.read())

