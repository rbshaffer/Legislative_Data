import re
import os
import codecs
from constitute_tools import parser

class _CountryBase:

    def __init__(self, file_path, content):

        self.file_path = file_path
        self.content = content

        print(content['id'])

    def parse(self):
        parsed = self._do_parse()
        self.content['parsed'] = parsed

    def _do_parse(self):
        return []


class UnitedStates(_CountryBase):
    def _do_parse(self):
        if self.content['subtype'] == 'resolution' or not re.search('(SECTION|SEC\. [0-9]+)', self.content['html']):
            return []
        else:
            cleaned = re.sub('\.--', '<title>\n', self.content['html'])
            cleaned = re.sub('``.*?\'\'|`.*?\'', '<snip>', cleaned, flags=re.DOTALL)
            cleaned = parser.clean_text(cleaned)

            start = re.search('(Be it enacted.*?)(SECTION|SEC\.)', cleaned, re.DOTALL)
            if start is not None:
                cleaned = cleaned[start.end(1):]
            end = re.search('(LEGISLATIVE HISTORY|Speaker of the House|' +
                            'Approved (January|February|March|April|May|June|' +
                            'July|August|September|October|November|December))', cleaned)
            if end is not None:
                cleaned = cleaned[:end.start()]

            temp_path = os.path.join('/tmp', os.path.basename(self.file_path))
            with codecs.open('/tmp/' + os.path.basename(self.file_path), 'wb', encoding='utf8') as f:
                f.write(cleaned)

            header_regex = ['(SECTION|SEC\.)\s*\.?\s*(&amp;lt;&amp;lt;NOTE: [0-9]+ USC [-0-9a-z]+\.?\s*' +
                            '(note)?\.?&amp;gt;&amp;gt;)?\s*[0-9]+\.\s*',
                            '\([a-z]\) ', '\([0-9]+\) ', '\([A-Z]\)']

            if re.search(header_regex[0], cleaned) is None:
                raw_input('FAILED PARSE')
                return []
            else:
                manager = parser.HierarchyManager(temp_path, header_regex, case_sensitive=True)
                manager.parse()

                out = manager.create_output('ccp')
                return out
