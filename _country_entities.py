import nltk as _nltk


class _EntityBase:
    def __init__(self, load_lstm):

        self.white_list = []
        self.black_list = []

        import sys

        if load_lstm:
            sys.path.append('/home/rbshaffer/sequence_tagging')

            from model.ner_model import NERModel
            from model.config import Config
            config = Config()

            # build model
            self.model = NERModel(config)
            self.model.build()
            self.model.restore_session(config.dir_model)

    def get_chunks(self, parsed):
        return []

    def do_entity_extraction(self, parsed):
        """ Somewhat complex function to actually do the entity extraction. """

        import networkx as nx
        import textwrap
        from numpy import mean

        chunks = self.get_chunks(parsed)

        def total_edge_count(count_obj, total_counter=0):
            """ Sub-function to calculate total number of edges in a container. """

            if count_obj:
                ceiling = count_obj.pop(count_obj.keys()[0])
                total_counter += sum([min(ceiling, count_obj[c]) for c in count_obj])
                total_counter = total_edge_count(count_obj, total_counter)

            return total_counter

        def observed_edge_count(raw_obj):
            """ Sub-function to calculate the observed number of edges in a container. """

            observed_counter = 0

            for chunk_obj in raw_obj:
                chunk_entities = {e: chunk_obj.count(e) for e in set(chunk_obj)}
                observed_counter += total_edge_count(chunk_entities)

            return observed_counter

        # container to store all entities extracted, for matching use in-string
        # maybe consider shifting this inside the loop to only match in-chunk?
        # though note that the output generator currently depends on this
        all_entities = []

        # output container
        out = []

        # iterate over units of analysis, as defined in country-specific functions
        for chunk in chunks:
            entity_strings = []

            sentences = self.process_doc(chunk)

            for sent in sentences:
                entities = []
                tags = self.model.predict(sent)

                for i, t in enumerate(tags):
                    if t == 'B-MISC':
                        entities.append([sent[i]])
                    elif t == 'I-MISC' and len(entities) > 0:
                        # this condition shouldn't be necessary - need to figure out why this is happening
                        entities[-1].append(sent[i])

                    #elif sent[i] in self.white_list and any([sent[i] in e.split() for e in all_entities]):
                    #    matches = [e for e in all_entities if sent[i] in e.split()]
                    #    entities.append([matches[-1]])

                new_entities = [' '.join(e) for e in entities]
                new_entities = ['\n'.join(textwrap.wrap(e.strip(), 20)) for e in new_entities]

                entity_strings += new_entities
                all_entities += new_entities

            out.append(entity_strings)

        # get the actual output
        entities_count = {e: all_entities.count(e) for e in set(all_entities)}

        out = [[e for e in row if e in entities_count] for row in out]

        edges = {}
        for chunk in out:
            if len(set(chunk)) > 1:
                entities = list(set(chunk))
                for i in range(len(entities)):
                    for j in range(i+1, len(entities)):
                        e1 = entities[i]
                        e2 = entities[j]

                        if (e1, e2) in edges:
                            edges[(e1, e2)] += min(chunk.count(e1), chunk.count(e2))
                        elif (e2, e1) in edges:
                            edges[(e2, e1)] += min(chunk.count(e1), chunk.count(e2))
                        else:
                            edges[(e1, e2)] = min(chunk.count(e1), chunk.count(e2))

        edges = [k + (w,) for k, w in edges.iteritems()]

        if entities_count:
            graph = nx.Graph()
            for u, v, w in edges:
                graph.add_edge(u, v, weight=w)

            degree = list(graph.degree(weight='weight').values())
            if degree:
                average_degree = mean(list(graph.degree(weight='weight').values()))
            else:
                average_degree = 0

            # count_zeroes?
            try:
                clustering_coeff = nx.average_clustering(graph, weight='weight', count_zeros=True)
            except ZeroDivisionError:
                clustering_coeff = 0

        else:
            graph = None
            clustering_coeff = None
            average_degree = None

        total_nodes = len(set(all_entities))
        total_edges = sum([e[2] for e in edges])

        return {'graph': graph, 'edges': edges, 'total_nodes': total_nodes, 'clustering': clustering_coeff,
                'total_edges': total_edges, 'average_degree': average_degree}

    @staticmethod
    def process_doc(document):

        sentences = _nltk.sent_tokenize(document)
        sentences = [_nltk.word_tokenize(sent) for sent in sentences]

        return sentences


class UnitedStates(_EntityBase):
    def __init__(self, load_lstm=True):
        _EntityBase.__init__(self, load_lstm)

    def get_chunks(self, parsed):
        i = 0
        chunks = ['']

        for row in parsed:

            if 'SECTION' in row[2] or 'SEC' in row[2]:
                i += 1
                chunks.append('')

            if row[4] != 'title':
                chunks[i] += ' ' + row[5]
                chunks[i].strip()

        return chunks
