__author__ = 'rbshaffer'


class _EntityBase:
    def __init__(self, parsed):
        import nltk

        self.parsed = parsed
        self.chunks = self.get_chunks()

        grammar = r"""
                    INST:
                    {<NNP|NNPS|POS>+(<NNP|NNPS|IN|CC|POS|,|DT>*<NNP|NNPS|POS>+)?}
                    }<CC><DT>{
                   """
        self.nnp = nltk.RegexpParser(grammar)
        self.stopwords = nltk.corpus.stopwords.words('english')

        self.white_list = []
        self.black_list = []

    def get_chunks(self):
        return []

    def process_entity(self, entity):
        return entity

    def do_entity_extraction(self):
        """ Somewhat complex function to actually do the entity extraction. """

        def total_edge_count(count_obj, total_counter=0):
            """ Sub-function to calculate total number of edges in a container. """
            if count_obj:
                ceiling = count_obj.pop(count_obj.keys()[0])
                total_counter += sum([min(ceiling, count_obj[k]) for k in count_obj])
                total_counter = total_edge_count(count_obj, total_counter)

            return total_counter

        def observed_edge_count(raw_obj):
            """ Sub-function to calculate the observed number of edges in a container. """
            observed_counter = 0
            for chunk_obj in raw_obj:
                chunk_entities = {e: chunk_obj.count(e) for e in set(chunk_obj)}
                observed_counter += total_edge_count(chunk_entities)
            return observed_counter

        import re
        import nltk
        import igraph

        # container to store all entities extracted, for matching use in-string
        # maybe consider shifting this inside the loop to only match in-chunk?
        # though note that the output generator currently depends on this
        all_entities = []

        # output container
        out = []

        # iterate over units of analysis, as defined in country-specific functions
        for chunk in self.chunks:
            entity_strings = []

            sentences = self.process_doc(chunk)

            for sent in sentences:
                extracted = self.nnp.parse(sent)
                entities = [r for r in extracted if type(r) == nltk.tree.Tree and r.label() == 'INST']

                for entity in entities:
                    entity_str = self.process_entity(entity)

                    # if the entity passes various screens (whitelist, blacklist, etc), add it to matches
                    if entity_str:
                        # if the entity is one word and white-listed:
                        # - take the last string that has a longer definition and add it
                        # - don't do this for 'state' or 'president since those usually aren't an issue
                        if entity_str in self.white_list and entity_str not in ['state', 'president', 'congress']\
                                and len(all_entities) > 0:
                            stub_matches = [entity_str] + [s for s in all_entities if entity_str in s.split()]
                            entity_str = stub_matches[-1]

                        # deal with case where two entities get crammed into one
                        # for now, assume there's only one repeat term - this might not work well!!!
                        repeat_whitelist_terms = [w for w in set(entity_str.split()) if w in self.white_list
                                                  and entity_str.split().count(w) > 1]
                        if len(repeat_whitelist_terms) > 0:
                            indices = [m.start() for m in re.finditer(repeat_whitelist_terms[0], entity_str)]
                            indices.insert(0, 0)
                            indices.append(len(entity_str))
                            for i in range(1, len(indices)):
                                split_entity = entity_str[indices[i-1]:indices[i]]

                                if split_entity:
                                    entity_strings.append(split_entity)
                                    all_entities.append(split_entity)
                        else:
                            entity_strings.append(entity_str)
                            all_entities.append(entity_str)

            out.append(entity_strings)

        # get the actual output
        entities_count = {e: all_entities.count(e) for e in set(all_entities)}

        # testing section to try deleting things that occur once
        # entities_count = {k: entities_count[k] for k in entities_count if entities_count[k] > 1}

        out = [[e for e in row if e in entities_count] for row in out]
        # end testing
        #
        # testing section to get edge data
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
            entities_found = True
        else:
            entities_found = False

        try:
            total_edges = total_edge_count(entities_count)
        except:
            total_edges = -1

        try:
            observed_edges = observed_edge_count(out)
        except:
            observed_edges = -1

        if total_edges > 0:
            return {'edges': edges, 'density': float(observed_edges)/float(total_edges), 'total_edges': total_edges}
        elif total_edges == 0 and entities_found:
            print '0 total edges; returning 1'
            return {'edges': edges, 'density': 1, 'total_edges': total_edges}
        else:
            return {'edges': None, 'density': None, 'total_edges': None}

    @staticmethod
    def process_doc(document):
        import nltk

        sentences = nltk.sent_tokenize(document)
        sentences = [nltk.word_tokenize(sent) for sent in sentences]

        # replace problematic words with a placeholder (e.g. period)
        problem_terms = ['or', 'by', 'under', 'an']
        sentences = [[w if w not in problem_terms else '(' for w in sent] for sent in sentences]
        sentences = [nltk.pos_tag(sent) for sent in sentences]

        return sentences


class UnitedStates(_EntityBase):
    def __init__(self, parsed):
        _EntityBase.__init__(self, parsed)

        self.white_list = ['secretary', 'committee', 'congress', 'service', 'council', 'board', 'senator',
                           'representative', 'united nations', 'institute', 'director', 'office', 'chairman',
                           'president', 'fund', 'officer', 'association', 'department', 'state', 'foundation', 'center',
                           'centers', 'senate', 'house', 'commission', 'agency', 'court', 'tribunal', 'survey',
                           'institutes', 'comptroller', 'forces', 'superintendent', 'inspector', 'government']
        self.black_list = ['act', 'code', 'amendments', 'document', 'amendment', 'statute', 'law', 'building',
                           'circular']

    def get_chunks(self):
        i = 0
        chunks = ['']

        for row in self.parsed:

            if 'SECTION' in row[2] or 'SEC' in row[2]:
                i += 1
                chunks.append('')

            if row[4] != 'title':
                chunks[i] += ' ' + row[5]
                chunks[i].strip()

        return chunks

    def process_entity(self, entity):
        import re
        import string

        entity_str = [w[0].strip(string.punctuation) for w in entity]
        entity_str = [w for w in entity_str if len(w) > 0]

        out = [w.lower() for w in entity_str if w.lower() not in self.stopwords]

        if (any([w in self.white_list for w in out]) or ' '.join(out) in self.white_list) and \
                all([w not in self.black_list for w in out]) and \
                re.search('[a-z]', ' '.join(entity_str)):

            return ' '.join(out)

        else:
            return None


