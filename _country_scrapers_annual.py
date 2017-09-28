import re as _re
from time import sleep as _sleep
from selenium import webdriver as _webdriver
from selenium.webdriver.support.ui import Select as _Select
from urllib2 import urlopen as _urlopen
from bs4 import BeautifulSoup as _BeautifulSoup


class _CountryBase:
    def __init__(self, log_data, country):
        self.data = {}
        self.new_ids = []

        self.log_data = log_data
        self.country = country

        for id_val in self._get_ids():
            if id_val not in self.log_data[self.country] and id_val is not None:
                self.new_ids.append(id_val)

    def iter_data(self):
        for id_val in self.new_ids:
            print id_val
            yield self._get_data(id_val)

            self.log_data[self.country].append(id_val)

    def _get_ids(self):
        return list()

    def _get_data(self, publication_id):
        return None


class Canada(_CountryBase):

    def _get_ids(self):
        """ Note structure here is a little different than later classes - metadata and IDs retrieved at same time. """

        def get_meta(bill_content):
            """ Get metadata search results based on a given URL. """

            title = bill_content.BillTitle.find(name='Title', language='en').text

            if 'amend' in title.lower():
                amend = True
            else:
                amend = False

            # rarely, no published version of a bill is available
            publication_tags = [t for t in bill_content.find_all('Publication')
                                if t.find(name='Title', language='en').text == 'Royal Assent']
            if len(publication_tags) == 1:
                publication_id = publication_tags[0]['id']
            else:
                publication_id = None

            # all other metadata appear to be consistently present
            date = bill_content.Events.LastMajorStageEvent.Event['date']
            session = bill_content.ParliamentSession['parliamentNumber']
            subtype = bill_content.BillType.find(name='Title', language='en').text
            sponsor = bill_content.SponsorAffiliation.Person.FullName.text
            sponsor_party = bill_content.SponsorAffiliation.PoliticalParty.find(name='Title', language='en').text
            majority_party = bill_content.PrimeMinister.PoliticalParty.find(name='Title', language='en').text

            committee_tags = bill_content.find_all(name='Committee', accronym=True)
            committee_names = [t['accronym'] for t in committee_tags]
            committee_data = {c: committee_names.count(c) for c in set(committee_names)}

            metadata = _format_meta_entry(country=u'canada',
                                          title=title,
                                          id=publication_id,
                                          date=date,
                                          session=session,
                                          type=u'annual',
                                          subtype=subtype,
                                          amendment=amend,
                                          sponsor=sponsor,
                                          sponsor_party=sponsor_party,
                                          majority_party=majority_party,
                                          hearings=committee_data)

            return metadata

        base_url = 'http://www.parl.gc.ca{0}'
        bill_types = ['/LegisInfo/Result.aspx?BillType=Senate%20Government%20Bill' +
                      '&BillStatus=RoyalAssentGiven&Language=E&Mode=1',
                      '/LegisInfo/Result.aspx?BillType=Private%20Member%E2%80%99s%20Bill' +
                      '&BillStatus=RoyalAssentGiven&Language=E&Mode=1',
                      '/LegisInfo/Result.aspx?BillType=House%20Government%20Bill' +
                      '&BillStatus=RoyalAssentGiven&Language=E&Mode=1',
                      '/LegisInfo/Result.aspx?BillType=Senate%20Public%20Bill']

        searches = []
        for bill_type in bill_types:
            search_content = _BeautifulSoup(_urlopen(base_url.format(bill_type)))
            sessions = [_re.sub('&Page=1', '&download=xml', tag['href']) for tag in search_content.find_all('a')
                        if _re.search('[0-9]{2}-[0-9]\s*\([0-9]+\)', tag.text) is not None]
            searches += sessions

        id_vals = []
        for s in searches:
            url = base_url.format(s)
            content = _BeautifulSoup(_urlopen(url).read(), features='xml')

            bills = content.find_all('Bill')
            for bill in bills:
                meta = get_meta(bill)

                if meta['id'] not in self.log_data['Canada']:
                    id_vals.append(meta['id'])
                    self.data[meta['id']] = meta

        return id_vals

    def _get_data(self, publication_id):
        from urllib2 import HTTPError

        def get_xml(xml_link):
            try:
                xml_data = _urlopen(xml_link).read()

                if 'xml' in xml_data[0:100]:
                    return xml_data
                else:
                    return None

            except HTTPError:
                return None

        def get_html(html_link):
            html_response = _urlopen(html_link)
            html_data = html_response.read()

            return html_data

        parl_url = 'http://www.parl.gc.ca'

        html_base = 'http://www.parl.gc.ca/HousePublications/Publication.aspx?Language=E&Mode=1&DocId={0}&Col=1'

        html_docs = []
        xml_docs = []

        initial_html = _urlopen(html_base.format(publication_id)).read()
        initial_soup = _BeautifulSoup(initial_html)
        full_doc_links = [tag for tag in initial_soup.find_all('a')
                          if 'Click here for the entire document' in tag.text]
        next_links = [tag for tag in initial_soup.find_all('a') if 'Next Page' in repr(tag)]

        full_link_success = False
        if len(full_doc_links) == 1:
            url = parl_url + full_doc_links[0]['href']
            try:
                print 'full link...'
                print publication_id, url
                html_local = get_html(url)
                xml_local = get_xml(url + '&xml=true')

                html_docs.append(html_local)
                xml_docs.append(xml_local)

                full_link_success = True
            except:
                pass

        next_link_success = False
        if full_link_success is False and len(next_links) > 0:
            try:
                while len(next_links) > 0:
                    file_regex = _re.search('File=[0-9]+', next_links[0]['href'])

                    # occasionally pages are malformed with "next" links that don't actually go anywhere
                    if file_regex is not None:
                        url = html_base.format(publication_id) + '&' + file_regex.group(0)
                        print 'next links...'
                        print publication_id, url

                        html_docs.append(get_html(url))
                        xml_docs.append(get_xml(url + '&xml=true'))

                        next_links = [tag for tag in _BeautifulSoup(html_docs[-1]).find_all('a')
                                      if 'Next Page' in repr(tag)]
                    else:
                        break
                next_link_success = True
            except:
                pass

        if full_link_success is False and next_link_success is False:
            print 'failsafe'
            print publication_id, html_base
            xml_docs.append(get_xml(html_base.format(publication_id) + '&xml=true'))
            html_docs.append(initial_html)

        self.data[publication_id].update({'html': html_docs, 'xml': xml_docs})
        return self.data[publication_id]


# class _Canada:
#     def __init__(self, log_data):
#         """
#         Scraper class to gather text and metadata from http://www.parl.gc.ca. Gathers metadata for all non-private bills
#         given royal assent based on a series of search results (turned into XML based on site tools), and then gathers
#         text results for those sites.
#
#         :param log_data: indexed by publication ID for royal assent
#         :return:
#         """
#
#         # urls to search for metadat
#         base_url = 'http://www.parl.gc.ca{0}'
#         bill_types = ['/LegisInfo/Result.aspx?BillType=Senate%20Government%20Bill' +
#                       '&BillStatus=RoyalAssentGiven&Language=E&Mode=1',
#                       '/LegisInfo/Result.aspx?BillType=Private%20Member%E2%80%99s%20Bill' +
#                       '&BillStatus=RoyalAssentGiven&Language=E&Mode=1',
#                       '/LegisInfo/Result.aspx?BillType=House%20Government%20Bill' +
#                       '&BillStatus=RoyalAssentGiven&Language=E&Mode=1',
#                       '/LegisInfo/Result.aspx?BillType=Senate%20Public%20Bill']
#
#         searches = []
#         for bill_type in bill_types:
#             search_content = _BeautifulSoup(_urlopen(base_url.format(bill_type)))
#             sessions = [tag['href'] for tag in search_content.find_all('a')
#                         if _re.search('[0-9]{2}\-[0-9]\s*\([0-9]+\)', tag.text) is not None]
#             searches += sessions
#
#         self.log_data = log_data
#
#         # scrape metadata based on XML search results
#         self.meta = []
#         for s in searches:
#             url = base_url.format(s)
#             self.meta += self.get_meta(url)
#
#     def iter_data(self):
#         for entry in self.meta:
#             if entry['id'] not in self.log_data['Canada'] and entry['id'] is not None:
#                 print entry['id']
#                 entry.update(self.get_text(entry['id']))
#                 yield entry
#
#                 self.log_data['Canada'].append(entry['id'])
#
#     @staticmethod
#     def get_meta(url):
#         """ Get metadata search results based on a given URL. """
#
#         import urllib
#         from bs4 import BeautifulSoup
#
#         out = []
#
#         # get the search results
#         result = urllib.urlretrieve(url)
#         with open(result[0], 'rb') as f:
#             content = BeautifulSoup(f.read(), features='xml')
#
#         # search over all bills, gather metadata from all available fields
#         bills = content.find_all('Bill')
#
#         for bill in bills:
#             title = bill.BillTitle.find(name='Title', language='en').text
#
#             if 'amend' in title.lower():
#                 amend = True
#             else:
#                 amend = False
#
#             # rarely, no published version of a bill is available
#             publication_tags = [tag for tag in bill.find_all('Publication')
#                                 if tag.find(name='Title', language='en').text == 'Royal Assent']
#             if len(publication_tags) == 1:
#                 publication_id = publication_tags[0]['id']
#             else:
#                 publication_id = None
#
#             # all other metadata appear to be consistently present
#             date = bill.Events.LastMajorStageEvent.Event['date']
#             session = bill.ParliamentSession['parliamentNumber']
#             subtype = bill.BillType.find(name='Title', language='en').text
#             sponsor = bill.SponsorAffiliation.Person.FullName.text
#             sponsor_party = bill.SponsorAffiliation.PoliticalParty.find(name='Title', language='en').text
#             majority_party = bill.PrimeMinister.PoliticalParty.find(name='Title', language='en').text
#
#             committee_tags = bill.find_all(name='Committee', accronym=True)
#             committee_names = [tag['accronym'] for tag in committee_tags]
#             committee_data = {c: committee_names.count(c) for c in set(committee_names)}
#
#             meta = _format_meta_entry(country=u'canada',
#                                       title=title,
#                                       id=publication_id,
#                                       date=date,
#                                       session=session,
#                                       type=u'annual',
#                                       subtype=subtype,
#                                       amendment=amend,
#                                       sponsor=sponsor,
#                                       sponsor_party=sponsor_party,
#                                       majority_party=majority_party,
#                                       hearings=committee_data)
#
#             out.append(meta)
#
#         return out
#
#     @staticmethod
#     def get_text(id_val):
#         """ Given a publication ID, grab the HTML and XML results, if any. """
#         import re
#         import urllib2
#         from bs4 import BeautifulSoup
#
#         def get_xml(xml_link):
#             try:
#                 xml_data = urllib2.urlopen(xml_link).read()
#
#                 if 'xml' in xml_data[0:100]:
#                     return xml_data
#                 else:
#                     return None
#
#             except urllib2.HTTPError:
#                 return None
#
#         def get_html(html_link):
#             html_response = urllib2.urlopen(html_link)
#             html_data = html_response.read()
#
#             return html_data
#
#         parl_url = 'http://www.parl.gc.ca'
#
#         html_base = 'http://www.parl.gc.ca/HousePublications/Publication.aspx?Language=E&Mode=1&DocId={0}&Col=1'
#
#         html_docs = []
#         xml_docs = []
#
#         initial_html = urllib2.urlopen(html_base.format(id_val)).read()
#         initial_soup = BeautifulSoup(initial_html)
#         full_doc_links = [tag for tag in initial_soup.find_all('a')
#                           if tag.text == 'Click here for the entire document']
#         next_links = [tag for tag in initial_soup.find_all('a') if 'Next Page' in repr(tag)]
#
#         if len(full_doc_links) == 1:
#             url = parl_url + full_doc_links[0]['href']
#
#             html_docs.append(get_html(url))
#             xml_docs.append(get_xml(url + '&xml=true'))
#
#         elif len(next_links) > 0:
#
#             while len(next_links) > 0:
#                 file_regex = re.search('File=[0-9]+', next_links[0]['href'])
#
#                 # occasionally pages are malformed with "next" links that don't actually go anywhere
#                 if file_regex is not None:
#                     url = html_base.format(id_val) + '&' + file_regex.group(0)
#
#                     html_docs.append(get_html(url))
#                     xml_docs.append(get_xml(url + '&xml=true'))
#
#                     next_links = [tag for tag in BeautifulSoup(html_docs[-1]).find_all('a')
#                                   if 'Next Page' in repr(tag)]
#                 else:
#                     break
#
#         else:
#             xml_docs.append(get_xml(html_base.format(id_val) + '&xml=true'))
#             html_docs.append(initial_html)
#
#         return {'html': html_docs, 'xml': xml_docs}
#
#
# class Australia(_CountryBase):
#
#     def _get_ids(self):
#
#         years = range(2004, 2017)
#         id_vals = []
#
#         driver = _webdriver.Firefox()
#
#         for year in years:
#             driver.get('https://www.legislation.gov.au/AdvancedSearch')
#
#             # configure the search results
#             id_search = driver.find_elements_by_class_name('rtsLink')[1]
#             id_search.click()
#
#             search_type = driver.find_element_by_name('ctl00$MainContent$QueryBuilder$rcbUniqueID')
#             search_type.send_keys('Register ID')
#
#             number_responses = driver.find_element_by_name('ctl00$MainContent$QueryBuilder$rcbResultsToAPage')
#             number_responses.send_keys('100 results to a page')
#
#             # do the search
#             search_field = driver.find_element_by_name('ctl00$MainContent$QueryBuilder$txtUniqueID')
#             search_field.send_keys('C' + str(year) + 'A*****')
#
#             execute = driver.find_element_by_name('ctl00$MainContent$QueryBuilder$btnSearch')
#             execute.click()
#
#             # walk through the results to get the id values
#             while True:
#                 legislation_ids = _re.findall('C[0-9]{4}A[0-9]{5}', driver.page_source)
#                 id_vals += list(set(legislation_ids))
#
#                 next_button = driver.find_element_by_class_name('rgPageNext')
#
#                 if not next_button.get_attribute('onclick'):
#                     next_button.click()
#                 else:
#                     break
#
#         return id_vals
#
#     def _get_data(self, publication_id):
#
#         max_attempts = 10
#         attempts = 0
#
#         soup = None
#
#         while attempts < max_attempts:
#             try:
#                 soup = _BeautifulSoup(_urlopen('https://www.legislation.gov.au/Details/{0}'.format(publication_id)))
#                 break
#             except:
#                 attempts += 1
#
#         # catch cases with dead links or missing text
#         if 'an error has occurred' in soup.text.lower() or 'help with file formats' in soup.text.lower():
#             meta = _format_meta_entry(id=publication_id)
#         else:
#             title = soup.find('title').text
#             date = [t for t in soup.find_all('td') if 'date of assent' in
#                     t.text.lower()][0].next_sibling.next_sibling.text
#
#             if 'amend' in title.lower():
#                 amend = True
#             else:
#                 amend = False
#
#             if 'no longer in force' in soup.text.lower():
#                 repealed = True
#             else:
#                 repealed = False
#
#             administrator = _re.search('Administrated By: +(.*?)', soup.text)
#             if administrator is not None:
#                 administrator = administrator.group(1).lower()
#
#             try:
#                 if len(soup.find_all('div', id='MainContent_RadPageHTML')) == 1:
#                     html_content = soup.find_all('div', id='MainContent_RadPageHTML')[0]
#                 else:
#                     html_content = [t for t in soup.find_all('a', attrs={'name': 'Text'})][0].next_sibling
#
#                 # force evaluation to make sure data was actually received
#                 html_content = unicode(html_content)
#             except RuntimeError:
#                 html_content = _urlopen('https://www.legislation.gov.au/Details/{0}'.format(publication_id)).read()
#                 html_content = _re.search('<PRE>.*</PRE>', html_content, flags=_re.DOTALL)
#                 if html_content is not None:
#                     html_content = html_content.group(0)
#
#             meta = _format_meta_entry(country=u'australia',
#                                       title=title,
#                                       id=publication_id,
#                                       date=date,
#                                       type=u'annual',
#                                       administrator=administrator,
#                                       repealed=repealed,
#                                       amendment=amend,
#                                       html=html_content)
#
#         return meta
#

class UnitedKingdom(_CountryBase):

    def _get_ids(self):
        id_vals = []
        years = range(1988, 2017)

        for year in years:
            soup = _BeautifulSoup(_urlopen('http://www.legislation.gov.uk/ukpga/{0}'.format(year)))
            n_results = _re.search('has returned ([0-9]+) results', soup.text.lower()).group(1)
            id_vals += [str(year) + '_' + str(i) for i in range(1, int(n_results) + 1)]

        return id_vals

    def _get_data(self, publication_id):

        max_attempts = 10
        attempts = 0

        xml_content = None
        soup = None

        while attempts < max_attempts:
            search_id = _re.sub('_', '/', publication_id)
            try:
                xml_content = _urlopen('http://www.legislation.gov.uk/ukpga/{0}/data.xml'.format(search_id)).read()
                soup = _BeautifulSoup(xml_content, 'xml')
                break
            except:
                attempts += 1

        if 'amendment' in soup.title.text.lower():
            amend = True
        else:
            amend = False

        if 'repeal' in soup.title.text.lower():
            repeal = True
        else:
            repeal = False

        if soup.EnactmentDate is not None:
            date = soup.EnactmentDate['Date']
        elif soup.PrimaryPrelims is not None:
            date = soup.PrimaryPrelims['RestrictStartDate']
        else:
            date = None
            print 'warning! No date found.'

        meta = _format_meta_entry(country=u'united_kingdom',
                                  title=soup.title.text,
                                  id=publication_id,
                                  date=date,
                                  type=u'annual',
                                  xml=xml_content,
                                  amendment=amend,
                                  repealed=repeal)

        return meta


class UnitedStates(_CountryBase):

    def _get_ids(self):
        # URL corresponding to the following search:
        # - All congresses from 1989 forward (first date with full bill text and metadata)
        # - Only legislation that can become law
        # - Only public bills/laws
        # - Only actual laws

        max_attempts = 10

        id_vals = []

        search_url = 'https://www.congress.gov/advanced-search/legislation?query=%7B%22congresses%22%3A%5B%22114%22%2C'\
                     '%22113%22%2C%22112%22%2C%22111%22%2C%22110%22%2C%22109%22%2C%22108%22%2C%22107%22%2C%22106%22%2C'\
                     '%22105%22%2C%22104%22%2C%22103%22%2C%22102%22%2C%22101%22%5D%2C%22restrictionType%22%3A%22field%'\
                     '22%2C%22restrictionFields%22%3A%5B%22billSummary%22%2C%22allBillTitles%22%5D%2C%22wordVariants%2'\
                     '2%3A%22true%22%2C%22legislationTypes%22%3A%5B%22hr%22%2C%22hjres%22%2C%22s%22%2C%22sjres%22%5D%2'\
                     'C%22legislationScope%22%3A%22Public%22%2C%22legislativeAction%22%3A%22115%22%2C%22legislativeAct'\
                     'ionWordVariants%22%3A%22true%22%2C%22sponsorTypes%22%3A%5B%22sponsor%22%2C%22sponsor%22%5D%2C%22'\
                     'sponsorTypeBool%22%3A%22Or%22%2C%22committeeBoolType%22%3A%22Or%22%2C%22legislationCanBecomeLaw%'\
                     '22%3A%22true%22%2C%22sponsorState%22%3A%22One%22%2C%22sourceTab%22%3A%22legislation%22%7D'

        driver = _webdriver.Firefox()
        driver.get(search_url)

        n_results = _Select(driver.find_element_by_name('pageSize'))
        n_results.select_by_visible_text('250 per page')

        while True:
            soup = _BeautifulSoup(driver.page_source)
            result_tags = [t for t in soup.find_all('span') if 'class' in t.attrs and 'result-heading' in t['class']]
            result_urls = list(set([t.a['href'] for t in result_tags]))

            new_ids = [_re.search('bill/(.*?)\?', url).group(1) for url in result_urls]
            new_ids = [_re.sub('/', '_', e) for e in new_ids]
            print new_ids
            id_vals += new_ids

            attempts = 0
            while attempts < max_attempts:
                try:
                    next_button = driver.find_element_by_class_name('next')
                    next_button.click()
                    _sleep(5)
                    break
                except:
                    print('reattempting pageforward...')
                    _sleep(5)
                    attempts += 1

            attempts = 0
            closed = False
            while attempts < max_attempts:
                print 'checking closure...'
                try:
                    closure_check = driver.find_element_by_class_name('next').get_attribute('outerHTML')
                    if 'next off' in closure_check:
                        closed = True

                    break
                except:
                    attempts += 1
                    print('reattempting closure check...')
                    _sleep(5)

            if closed:
                break

        return id_vals

    def _get_data(self, publication_id):
        import bs4
        
        search_term = _re.sub('_', '/', publication_id)

        text_soup = None
        text_content = None

        try:
            text_url = 'https://www.congress.gov/bill/{0}/text'.format(search_term)
            text_soup = _BeautifulSoup(_urlopen(text_url))
        except:
            pass

        if text_soup is not None:
            if text_soup.find('pre') is not None:
                text_content = str(text_soup.find('pre'))
            else:
                text_content = str(text_soup.find('table', attrs={'class': 'lbexTableStyleEnr'}))

        meta_url = 'https://www.congress.gov/bill/{0}/all-info'.format(search_term)
        meta_soup = _BeautifulSoup(_urlopen(meta_url))

        title = _re.search(': (.*)', meta_soup.find('meta', attrs={'name': 'dc.title'})['content'])
        if title is not None:
            title = title.group(1)

        date = meta_soup.find('meta', attrs={'name': 'dc.date'})['content']
        sponsor = meta_soup.find('meta', attrs={'name': 'dc.creator'})
        if sponsor is not None:
            sponsor = sponsor['content']

            sponsor_party = _re.search(sponsor + ' \[([A-Z])', meta_soup.text)
            if sponsor_party is not None:
                sponsor_party = sponsor_party.group(1)
        else:
            sponsor_party = None

        cosponsors = [tag.text for tag in meta_soup.find_all('a', href=True)
                      if 'member/' in tag['href'] and sponsor not in tag.text]

        policy_area = _re.search('Policy Area:\s*(.*)', meta_soup.text)
        if policy_area is not None:
            policy_area = policy_area.group(1)

        committee_entries = meta_soup.find_all('tr', class_='committee')
        referred = [entry.find('th').text for entry in committee_entries]
        hearings_held = []

        for entry in committee_entries:
            committee_name = entry.find('th').text
            actions = [entry.find_all('td')[1].text]

            entry = entry.next_sibling
            while type(entry) == bs4.element.Tag and ('class' not in entry.attrs or 'committee' not in entry['class']):
                actions.append(entry.find_all('td')[1].text)
                entry = entry.next_sibling

                if type(entry) == bs4.element.NavigableString:
                    break

            hearings = [action for action in actions if 'Hearing' in action]
            hearings_held += [committee_name]*len(hearings)

        if 'amend' in title:
            amendment = True
        else:
            amendment = False

        if 'resolution' in publication_id:
            subtype = u'resolution'
        else:
            subtype = u'law'

        meta = _format_meta_entry(country=u'united_states',
                                  title=title,
                                  id=publication_id,
                                  date=date,
                                  type=u'annual',
                                  subtype=subtype,
                                  amendment=amendment,
                                  sponsor=sponsor,
                                  sponsor_party=sponsor_party,
                                  cosponsors=cosponsors,
                                  referred=referred,
                                  hearings=hearings_held,
                                  policy_area=policy_area,
                                  html=text_content)

        return meta


def _format_meta_entry(**kwargs):
    fields = ['country', 'title', 'id', 'date', 'session', 'type', 'subtype', 'amendment', 'sponsor', 'sponsor_party',
              'cosponsors', 'majority_party', 'majority_size', 'referred', 'hearings', 'policy_area', 'administrator',
              'repealed', 'xml', 'html']

    meta_entry = {field: kwargs.get(field, None) for field in fields}
    return meta_entry
