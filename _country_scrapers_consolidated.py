import json as _json
import tempfile as _tempfile
import os as _os
import re as _re
import urllib as _urllib
import urllib2 as _urllib2
import zipfile as _zipfile
from bs4 import BeautifulSoup as _BeautifulSoup


class _CountryBase:
    def __init__(self, log_data, country, base_path):
        self.new_ids = []

        self.log_data = log_data
        self.country = country
        self.data_path = _os.path.join(base_path, 'Legislation', country, 'Consolidated')

        if 'Consolidated' not in self.log_data:
            self.log_data['Consolidated'] = {}

        for id_val in self._get_version_ids():
            if id_val not in self.log_data['Consolidated']:
                self.new_ids.append(id_val)

    def update_code(self):
        for id_val in self.new_ids:
            print(id_val)

            self._get_code_version(id_val)
            self._extract_code(id_val)

            self.log_data['Consolidated'][self.country].append(id_val)

    def _get_version_ids(self):
        return list()

    def _get_code_version(self, publication_id):
        pass

    def _extract_code(self, publication_id):
        return None


class UnitedStates(_CountryBase):
    def _get_version_ids(self):
        base_url = 'http://uscode.house.gov/download/annualhistoricalarchives/downloadxhtml.shtml'
        soup = _BeautifulSoup(_urllib2.urlopen(base_url))

        tags = [t for t in soup.find_all('a') if '.zip' in t['href']]

        id_vals = [_re.search('[0-9]+', t['href']).group(0) for t in tags]

        return id_vals

    def _get_code_version(self, publication_id):
        dl_url = 'http://uscode.house.gov/download/annualhistoricalarchives/XHTML/' + publication_id + '.zip'
        zip_path = _os.path.join(_tempfile.gettempdir(), self.country + publication_id + '.zip')

        _urllib.urlretrieve(dl_url, zip_path)

        with _zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(_tempfile.gettempdir())

        _os.remove(zip_path)

    def _extract_code(self, publication_id):
        def section_parser(soup):
            def num_search(tag):
                return _re.search('[0-9]+[a-z]*\.', tag.text).group(0)

            section_head = soup.find('h3', class_='section-head')
            next_tag = section_head.find_next_sibling(['h3', 'p'])

            section_number = num_search(section_head)

            out = {section_number: []}

            while next_tag:
                if 'class' in next_tag.attrs and 'section-head' in next_tag['class'][0]:
                    section_head = next_tag
                    section_number = num_search(section_head)

                    out[section_number] = []

                else:
                    if 'class' in next_tag.attrs and 'statutory' in next_tag['class'][0]:
                        out[section_number].append(next_tag.text)

                next_tag = next_tag.find_next_sibling(['h3', 'p'])

            return out

        def get_chapter(ch):
            if ch in current_chapters:
                with open(_os.path.join(self.data_path, ch)) as fname:
                    ch_data = _json.loads(fname)
            else:
                ch_data = {}

            return ch_data

        temp_folder = _os.path.join(_tempfile.gettempdir(), publication_id)
        chapters = [f for f in _os.listdir(temp_folder) if _re.search('[0-9]+usc[0-9]+[a-z]?\.htm', f)]

        current_chapters = _os.listdir(self.data_path)

        for ch_name in chapters:
            chapter_data = get_chapter(ch_name)

            with open(_os.path.join(temp_folder, ch_name)) as f:
                chapter_soup = _BeautifulSoup(f.read())
                sections = section_parser(chapter_soup)

            for s in sections:
                if s in chapter_data:
                    chapter_data[s][publication_id] = sections[s]
                else:
                    chapter_data[s] = {publication_id: sections[s]}

            with open(_os.path.join(self.data_path, ch_name)) as f:
                f.write(_json.dumps(chapter_data))

        _os.rmdir(temp_folder)