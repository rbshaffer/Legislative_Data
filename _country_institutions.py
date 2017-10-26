import json as _json
import string as _string
import re as _re
import wikipedia as _wikipedia
from urllib2 import urlopen as _urlopen
from bs4 import BeautifulSoup as _BeautifulSoup


class _CountryBase:
    def __init__(self, country):
        self.agency_dictionary = {}
        self.training_data = []
        self.country = country

    def update(self):
        return None


class UnitedStates(_CountryBase):
    def update(self):
        """
        Generate a whitelist of institution names, based on three sources: usa.gov, federalregister.gov, and wikipedia.
        Do a little bit of preprocessing on the lists of names to make them usable, and output those names as a list.
        """

        self._update_wikipedia()
        self._update_usa()
        self._update_register()

    @staticmethod
    def _preprocess_name(name_str):
        isascii = lambda s: len(s) == len(s.encode(errors='ignore'))

        name_str = _re.sub('\(.*?\)|^U\.S\.|^USA?|^United States|of the United States$', '', name_str)
        name_str = name_str.strip()

        if ', ' in name_str:
            name_str = name_str.split(', ')[1] + ' ' + name_str.split(', ')[0]

        if _re.search('(Senate|House|Joint) Committee', name_str):
            name_str = _re.sub('(Senate|House|Joint)', '', name_str)

        name_str = ''.join([c for c in name_str if isascii(c)])
        name_str = name_str.strip()

        return name_str

    def _update_usa(self):
        """
        Update whitelist based on usa.gov
        """
        print 'Getting agencies from usa.gov...'

        url_base = 'https://www.usa.gov'
        letters = _string.ascii_lowercase

        agency_dic = {}

        for letter in letters:
            url = url_base + '/federal-agencies/' + letter
            soup = _BeautifulSoup(_urlopen(url).read())

            links_content = [l for l in soup.find_all('ul') if 'class' in l.attrs and 'one_column_bullet' in l['class']]
            if len(links_content) == 1:
                links_list = links_content[0].find_all('a')
                for agency_html in links_list:
                    name_short = self._preprocess_name(agency_html.string)
                    agency_dic[name_short] = {'html': agency_html,
                                              'url': url_base + agency_html['href'],
                                              'name_full': agency_html.string,
                                              'source': 'usa.gov'}

                    print agency_html.string

            elif len(links_content) == 0:
                pass

            else:
                raise ValueError('Too many list elements found! Please modify the HTML parser.')

        self.agency_dictionary.update(agency_dic)

    def _update_register(self):
        print 'Getting agencies from the federal register...'

        url_base = 'https://www.federalregister.gov/agencies'
        soup = _BeautifulSoup(_urlopen(url_base))
        links = soup.find_all(lambda x: x.name == 'li' and x.has_attr('data-filter-live') and not x.has_attr('class'))

        agency_dic = {}

        for link in links:
            agency = link.find('a')
            name_short = self._preprocess_name(agency.string)
            agency_dic[name_short] = {'html': agency,
                                      'url': agency['href'],
                                      'name_full': agency.string,
                                      'source': 'federal_register'}

            print agency.string

        self.agency_dictionary.update(agency_dic)

    def _update_wikipedia(self):
        # do a little bit of name preprocessing here too
        from requests import ConnectionError

        print 'Getting data from Wikipedia...'

        page_current = _wikipedia.page('List_of_federal_agencies_in_the_United_States')
        html = page_current.html()
        subset = html[_re.search('<h2>.*?Legislative Branch', html).start():_re.search('<h2>.*?See also', html).start()]
        soup = _BeautifulSoup(subset)

        links = soup.find_all(lambda x: x.name == 'a' and x.has_attr('href') and '/wiki/' in x['href'] and
                              'File:' not in x['href'])

        agency_dic = {self._preprocess_name(link['title']): {'html': link,
                                                             'url': 'https://en.wikipedia.org' + link['href'],
                                                             'name_full': link['title'],
                                                             'source': 'wikipedia'}
                      for link in links}

        category_pages = ['https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&' +
                          'cmtitle=Category:Defunct_agencies_of_the_United_States_government&cmlimit=500&format=json',
                          'https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&' +
                          'cmtitle=Category:Committees_of_the_United_States_Senate&cmlimit=500&format=json',
                          'https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&' +
                          'cmtitle=Category:Joint_committees_of_the_United_States_Congress' +
                          '&cmlimit=500&format=json',
                          'https://en.wikipedia.org/w/api.php?action=query&list=categorymembers&' +
                          'cmtitle=Category:Committees_of_the_United_States_House_of_Representatives' +
                          '&cmlimit=500&format=json',
                          ]

        for category_page in category_pages:
            content_defunct = _json.loads(_urlopen(category_page).read())

            for result in content_defunct['query']['categorymembers']:
                if result['ns'] == 0:
                    url_defunct = 'https://en.wikipedia.org/wiki/' + _re.sub(' ', '_', result['title'])
                    print(result['title'])
                    try:
                        page_defunct = _wikipedia.page(result['title'])

                        name_short = self._preprocess_name(result['title'])

                        agency_dic[name_short] = {'html': page_defunct.html(),
                                                  'url': url_defunct,
                                                  'name_full': result['title'],
                                                  'source': 'wikipedia'}

                    except ConnectionError:
                        print('Failed to get agency HTML!')

        self.agency_dictionary.update(agency_dic)
