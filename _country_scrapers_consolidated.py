import json as _json
import os as _os
import re as _re
import shutil as _shutil
import tempfile as _tempfile
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
            self.log_data['Consolidated'] = {country: []}

        for id_val in self._get_version_ids():
            if id_val not in self.log_data['Consolidated'][country]:
                self.new_ids.append(id_val)

        # change here later - 2017 not complete
        self.new_ids = [id_val for id_val in self.new_ids if id_val != '2017']

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
        def parser(soup):
            def section_num_search(tag):
                id_val = _re.search(u'^\s*\xa7([0-9]+[-\u2014\u2013a-zA-Z0-9]*)', tag.text).group(1).lower()
                return {'id': id_val}

            def chapter_num_search(tag):
                print(tag)
                regex = _re.search(u'chapter ([0-9a-z]+)\u2014?(.*)', tag.text.lower())
                id_val = regex.group(1)
                name = regex.group(2)
                return {'id': id_val, 'name': name}

            headers_to_exclude = ['omitted', 'repealed', 'transferred', 'renumbered', 'vacant']
            # next_tag = soup.find('h3', text=lambda t: t and _re.search('chapter[^s]', t.lower()))

            out = []
            i = None

            # if next_tag:
            #     chapter_regex = chapter_num_search(next_tag)
            #     chapter_name = chapter_regex['name']
            #     chapter_id = chapter_regex['id']
            #
            #     next_tag = next_tag.find_next('h3',
            #                                   class_='section-head',
            #                                   text=lambda t: t and all([excl not in t.lower() for
            #                                                             excl in headers_to_exclude])
            #                                                     and _re.search('^\s*\xa7[^\xa7]', t))
            #     if next_tag:
            #         section_regex = section_num_search(next_tag)
            #         section_id = section_regex['id']
            #
            #         next_tag = next_tag.find_next(['h3', 'p'])
            #
            #         out.append({'name': chapter_name,
            #                     'id': chapter_id,
            #                     'parsed': {section_id: []}})

            next_tag = soup.find('h3')

            while next_tag:
                chapter_bool = next_tag.name == 'h3' and next_tag.find('strong') and not \
                    next_tag.find('sup') and _re.search('^chapter[^s]', next_tag.text.lower())
                section_bool = next_tag.name == 'h3' and \
                               'class' in next_tag.attrs and next_tag['class'][0] == 'section-head'

                valid_section_bool = all([excl not in next_tag.text.lower() for excl in headers_to_exclude]) \
                                     and _re.search('^\s*\xa7[^\xa7]', next_tag.text)
                par_bool = next_tag.name == 'p' and 'class' in next_tag.attrs and \
                           'statutory' in next_tag['class'][0]

                if chapter_bool:
                    if i is None:
                        i = 0
                    else:
                        i += 1

                    chapter_regex = chapter_num_search(next_tag)
                    chapter_name = chapter_regex['name']
                    chapter_id = chapter_regex['id']

                    out.append({'name': chapter_name,
                                'id': chapter_id,
                                'parsed': {}})

                    next_tag = next_tag.find_next(['h3', 'p'])
                elif len(out) > 0:
                    if section_bool:
                        if valid_section_bool:
                            section_regex = section_num_search(next_tag)
                            section_id = section_regex['id']

                            out[i]['parsed'][section_id] = []

                            next_tag = next_tag.find_next(['h3', 'p'])

                        else:
                            next_tag = next_tag.find_next('h3')

                    elif par_bool:
                        out[i]['parsed'][section_id].append(next_tag.text)
                        next_tag = next_tag.find_next(['h3', 'p'])

                    else:
                        next_tag = next_tag.find_next(['h3', 'p'])
                else:
                    next_tag = next_tag.find_next('h3')

            return out

        temp_folder = _os.path.join(_tempfile.gettempdir(), publication_id)
        titles = [fname for fname in _os.listdir(temp_folder) if _re.search('[0-9]+usc[0-9]+[a-z]?\.htm', fname)]

        # filter out appendix titles
        titles = [fname for fname in titles if not _re.search('[0-9]+a', fname)]

        for title in titles:
            with open(_os.path.join(temp_folder, title)) as f:
                title_soup = _BeautifulSoup(f.read())

            title_parsed = parser(title_soup)

            title_id = _re.sub('^[0-9]+usc|\.htm', '', title)
            title_folder = _os.path.join(self.data_path, title_id)
            if not _os.path.isdir(title_folder):
                _os.mkdir(title_folder)

            for chapter in title_parsed:
                out_name = '_'.join([chapter['id'], publication_id]) + '.json'
                out_path = _os.path.join(self.data_path, title_id, out_name)

                to_write = {'country': u'united_states',
                            'date': publication_id,
                            'id': u'_'.join([title_id, chapter['id']]),
                            'type': u'consolidated',
                            'title': chapter['name'],
                            'parsed': chapter['parsed']}

                with open(out_path, 'w') as f:
                    f.write(_json.dumps(to_write))

        _shutil.rmtree(temp_folder)
