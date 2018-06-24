import cStringIO
import codecs
import csv
import json
import os
import re
from datetime import datetime


class DataManager:
    def __init__(self, wrk_dir):
        """
        Overall manager class, to handle scraped data. Upon initialization, creates the file structure to hold the
        output at the given working directory and builds a log file to record which files have been downloaded. Indexing
        within the log is country-specific, to reflect the numbering systems used by each country-level database.

        :param wrk_dir: directory at which to create the file structure.
        :return:
        """

        self.wrk_dir = wrk_dir.rstrip(os.sep)

        if not os.path.exists(self.wrk_dir):
            raise OSError('The given working directory does not exist!')
        else:
            self.data_path = os.path.join(self.wrk_dir, 'Legislative_Data')
            self.log_path = os.path.join(self.wrk_dir, 'Legislative_Data', 'log.json')
            if not os.path.exists(self.data_path):
                os.mkdir(self.data_path)
                os.mkdir(os.path.join(self.data_path, 'Legislation'))

            if not os.path.exists(self.log_path):
                log_data = {'last updated': None}

                with open(self.log_path, 'wb') as f:
                    f.write(json.dumps(log_data))

            else:
                with open(self.log_path, 'rb') as f:
                    log_data = json.loads(f.read())

        self.log_data = log_data

    def update_annual(self):
        """
        Wrapper function to run the various scrapers contained in the package and write the outputs. Also sets up file
        structure for output within each country. Initializes each scraper, and updates on-disk dataset based on the
        log file.

        Each scraper should have a scraper.data attribute which consists of a list of dictionaries, each of
        which holds metadata and text for each piece of legislation. Each entry should, at minimum, have a unique 'id'
        key, which is used to generate the file path for the output.
        """

        import _country_scrapers_annual

        self.log_data['last updated'] = datetime.now().strftime('%m/%d/%Y')

        countries = [c for c in dir(_country_scrapers_annual) if '_' not in c]

        for country in countries:
            # initialize the file structure if working with a new country
            print(country)

            self._initialize_folders(country)

            # Initialize the scraper for annual legislation for a given country, and write the output
            scraper = getattr(_country_scrapers_annual, country)(self.log_data, country)
            for entry in scraper.iter_data():
                out_path = os.path.join(self.data_path, 'Legislation',
                                        country.strip('_'), 'Annual',
                                        entry['id']) + '.json'

                with open(out_path, 'wb') as f:
                    f.write(json.dumps(entry))

                self.log_data = scraper.log_data

                # write the updated log
                with open(self.log_path, 'wb') as f:
                    f.write(json.dumps(self.log_data))

    def update_consolidated(self):
        """
        Wrapper function to scrape consolidated code files. Currently only implemented for the United States.

        """
        import _country_scrapers_consolidated

        self.log_data['last updated'] = datetime.now().strftime('%m/%d/%Y')

        countries = [c for c in dir(_country_scrapers_consolidated) if '_' not in c]

        for country in countries:
            print(country)

            self._initialize_folders(country)
            print(self.log_data.keys())
            scraper = getattr(_country_scrapers_consolidated, country)(self.log_data, country, self.data_path)
            scraper.update_code()

            self.log_data = scraper.log_data

            # write the updated log
            with open(self.log_path, 'wb') as f:
                f.write(json.dumps(self.log_data))

    def append_parsed(self):
        import _country_parsers_annual

        _country_scrapers_annual = reload(_country_parsers_annual)

        countries = [c for c in dir(_country_scrapers_annual) if re.search('^[A-Z]', c)]

        base_dir = os.path.join(self.data_path, 'Legislation', '{0}', 'Annual')

        for country in countries:
            country_dir = base_dir.format(country)
            file_list = os.listdir(country_dir)

            for file_name in file_list:
                full_path = os.path.join(country_dir, file_name)
                with open(full_path, 'rb') as f:
                    content = json.loads(f.read())

                manager = getattr(_country_parsers_annual, country)(full_path, content)
                manager.parse()

                with open(full_path, 'wb') as f:
                    f.write(json.dumps(manager.content))

    def append_auxiliary(self):
        import _country_auxiliary_annual

        countries = [c for c in dir(_country_auxiliary_annual) if '_' not in c]
        base_dir = os.path.join(self.data_path, 'Legislation', '{0}', 'Annual')
        aux_dir = os.path.join(self.data_path, 'Auxiliary')

        for country in countries:
            country_path = base_dir.format(country)
            file_list = [os.path.join(country_path, f) for f in os.listdir(country_path) if 'resolution' not in f]

            appender = getattr(_country_auxiliary_annual, country)(file_list, aux_dir, country)
            appender.add_auxiliary()

    def extract_entities_annual(self, write=True):
        import _country_entities

        # change here as necessary to implement more countries later
        countries = ['UnitedStatesAnnual']

        base_dir = os.path.join(self.data_path, 'Legislation', '{0}', 'Annual')
        out_path = os.path.join(self.data_path, 'Out', 'out_annual.csv')

        out = []

        for country in countries:
            parser = getattr(_country_entities, country)()

            country_dir = base_dir.format(re.sub('Annual', '', country))
            file_list = [os.path.join(country_dir, f) for f in os.listdir(country_dir) if 'resolution' not in f]

            for file_name in file_list:
                print(re.sub('_', '/', file_name).strip('.json'))

                with open(file_name, 'rb') as in_f:
                    content = json.loads(in_f.read())

                    if content['parsed']:
                        parsed = parser.do_entity_extraction(content['parsed'])

                        keys_to_add = ['total_nodes', 'total_edges', 'clustering', 'average_degree']
                        null_keys = ['cosponsors', 'hearings', 'referred']

                        content.update({k: parsed[k] for k in keys_to_add})
                        content.update({k: len(content[k]) if content[k] else 0 for k in null_keys})

                        out.append(content)

                        # writing as output is generated for safety
                        if write:
                            with open(out_path, 'a') as out_f:
                                writer = csv.DictWriter(out_f,
                                                        fieldnames=['id', 'date', 'title', 'clustering', 'total_nodes',
                                                                    'total_edges', 'average_degree', 'topic', 'sponsor',
                                                                    'dw',
                                                                    'sponsor_party', 'sponsor_majority', 'cosponsors',
                                                                    'hearings', 'referred', 'control',
                                                                    'president_party', 'commemorative'],
                                                        extrasaction='ignore')

                                if len(out) == 1:
                                    writer.writeheader()

                                writer.writerow(out[-1])

        # overwriting the whole thing at the end - probably not necessary
        if write:
            with open(out_path, 'wb') as f:
                writer = csv.DictWriter(f, fieldnames=['id', 'date', 'title', 'clustering', 'total_nodes',
                                                       'total_edges', 'average_degree', 'topic', 'sponsor', 'dw',
                                                       'sponsor_party', 'sponsor_majority', 'cosponsors',
                                                       'hearings', 'referred', 'control',
                                                       'president_party', 'commemorative'],
                                        extrasaction='ignore')
                writer.writeheader()
                writer.writerows(out)

    def extract_entities_consolidated(self, write=True):
        from networkx.readwrite import json_graph
        import _country_entities

        # change here as necessary to implement more countries later
        countries = ['UnitedStatesConsolidated']

        # update if more years are added
        years = [str(yr) for yr in range(1994, 2018)]

        base_dir = os.path.join(self.data_path, 'Legislation', '{0}', 'Consolidated')
        out_dir = os.path.join(self.data_path, 'Out')

        out_path = os.path.join(out_dir, 'out_consolidated.csv')

        fieldnames = ['id', 'date', 'title', 'clustering', 'total_nodes', 'total_edges', 'average_degree']

        out = []

        for country in countries:
            entity_parser = getattr(_country_entities, country)()

            country = re.sub('Consolidated', '', country)
            country_dir = base_dir.format(country)
            title_list = os.listdir(country_dir)

            for title in title_list:
                print('Title: ' + title)

                title_dir = os.path.join(country_dir, title)
                chapter_list = os.listdir(title_dir)

                previous_chapter_id = None
                entities_data = {}

                for chapter_file in sorted(chapter_list):
                    print(chapter_file)
                    chapter_id, year = re.search('(.*?)_([0-9]{4})', chapter_file).groups()

                    chapter_path = os.path.join(title_dir, chapter_file)
                    with open(chapter_path, 'rb') as f:
                        current_chapter = json.loads(f.read())

                    if current_chapter['parsed']:
                        if chapter_id != previous_chapter_id:
                            previous_chapter_id = chapter_id
                            entities_data = entity_parser.do_entity_extraction(current_chapter['parsed'])
                        else:
                            previous_chapter_paths = [os.path.join(title_dir, '_'.join([chapter_id, str(yr)])) + '.json'
                                                      for yr in list(reversed(range(1994, int(year))))]

                            entitites_data = {}

                            for previous_chapter_path in previous_chapter_paths:
                                if os.path.isfile(previous_chapter_path):
                                    with open(previous_chapter_path, 'rb') as f:
                                        previous_chapter = json.loads(f.read())

                                    # implicitly leaves entity data the same as the previous step if text unchanged
                                    if previous_chapter['parsed'] == current_chapter['parsed']:
                                        current_chapter.update({k: out[-1][k] for k in fieldnames
                                                                if k not in current_chapter})
                                        break

                            if not all([fieldname in current_chapter for fieldname in fieldnames]):
                                entities_data = entity_parser.do_entity_extraction(current_chapter['parsed'])

                        current_chapter.update({k: str(entities_data[k]) for k in fieldnames
                                                if k not in current_chapter})
                        out.append({k: current_chapter[k] for k in current_chapter if k in fieldnames})

                        graph_dir = os.path.join(out_dir, 'consolidated_graphs', title)
                        if not os.path.isdir(graph_dir):
                            os.makedirs(graph_dir)

                        with open(os.path.join(graph_dir, chapter_id + '_' + year + '.json'), 'w') as f:
                            if entities_data['graph']:
                                f.write(json.dumps(json_graph.adjacency_data(entities_data['graph'])))
                            else:
                                f.write('')

                        # writing as output is generated for safety
                        if write:
                            with open(out_path, 'a') as f:
                                writer = DictUnicodeWriter(f, fieldnames=fieldnames)
                                if os.path.getsize(out_path) == 0:
                                    writer.writeheader()

                                writer.writerow(out[-1])

        # overwriting the whole thing at the end - probably not necessary
        if write:
            with open(out_path, 'wb') as f:
                writer = DictUnicodeWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(out)


    def _initialize_folders(self, country):
        base_country_path = os.path.join(self.data_path, 'Legislation', country.strip('_'))

        try:
            os.mkdir(base_country_path)
        except OSError:
            pass

        try:
            os.mkdir(os.path.join(base_country_path, 'Annual'))
        except OSError:
            pass

        try:
            os.mkdir(os.path.join(base_country_path, 'Consolidated'))
        except OSError:
            pass


class Visualize:
    def __init__(self, wrk_dir, country):
        import _country_entities

        # some test examples
        # file_name = '111th-congress_house-bill_1.json'
        # file_name = '111th-congress_senate-bill_1707.json'

        self.wrk_dir = wrk_dir.rstrip(os.sep)
        self.parser = getattr(_country_entities, country)()

        self.G = None
        self.edges = None

    def analyze(self, path, out_path=None):
        import networkx as nx

        with open(os.path.join(self.wrk_dir, path), 'rb') as f:
            content = json.loads(f.read())

        parsed = self.parser.do_entity_extraction(content['parsed'])

        self.G = parsed['graph']
        self.edges = parsed['edges']

        eigs = nx.eigenvector_centrality(self.G, weight='weight')

        print 'Centrality:'
        print zip(sorted(eigs, key=eigs.get, reverse=True), sorted(eigs.values(), reverse=True))
        print nx.average_clustering(self.G, weight='weight')

        if out_path:
            with open(out_path, 'w') as f:
                csv.writer(f).writerows(self.edges)

    def draw(self, labels=True):
        import matplotlib.pyplot as plt
        import networkx as nx

        pos = nx.nx_pydot.graphviz_layout(self.G)

        plt.figure(figsize=(10, 10))
        nx.draw_networkx_nodes(self.G, pos, node_size=15, alpha=0.5, node_color='black')

        m = float(max([e[2] for e in self.edges]))
        for edge in self.edges:
            edge_list = [[edge[0], edge[1]]]
            nx.draw_networkx_edges(self.G, pos, edgelist=edge_list, width=10*(edge[2]/m)**2, alpha=0.3,
                                   edge_color='b')
        if labels:
            nx.draw_networkx_labels(self.G, pos, font_size=10, font_family='sans-serif')

        plt.axis('off')
        # plt.draw()
        # raw_input('')
        # plt.close()
        plt.savefig("/home/rbshaffer/Desktop/fig1.pdf", dpi=500)


class DictUnicodeWriter(object):
    def __init__(self, f, fieldnames, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.DictWriter(self.queue, fieldnames, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, D):
        self.writer.writerow({k: v.encode("utf-8") for k, v in D.items()})
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for D in rows:
            self.writerow(D)

    def writeheader(self):
        self.writer.writeheader()
