
class RagePrinter():
    def __init__(self):
        self._depth = 0
        self._lines = []

    def add(self, text):
        indent = self._depth * 2 * ' '
        if not text:
            indent = ''
        self._lines.append(f'{indent}{text}')
        return self

    def next(self):
        self._depth += 1
        return self
    
    def prev(self):
        self._depth -= 1
        return self

    def print(self):
        for line in self._lines:
            print(line)

    def save(self, outfile):
        with open(outfile, 'w') as f:
            f.write('\n'.join(self._lines))
        self._lines = []
