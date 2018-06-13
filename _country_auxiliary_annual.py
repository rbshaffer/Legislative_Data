__author__ = 'rbshaffer'


class _AuxiliaryBase:
    def __init__(self, file_list, aux_path, country):
        import os
        self.file_list = file_list
        self.country = country
        self.aux_files = [os.path.join(aux_path, f) for f in os.listdir(aux_path) if self.country in f]

    def add_auxiliary(self):
        import re
        import json

        auxiliary = self._retrieve_auxiliary()
        for file_name in self.file_list:
            with open(file_name, 'rb') as f:
                content = json.loads(f.read())

            print content['id']
            congress = re.search('^[0-9]+', content['id']).group(0)
            chamber = re.search('house|senate', content['id']).group(0)
            id_val = re.search('[0-9]+$', content['id']).group(0)

            if content['id'] in auxiliary:
                content.update(auxiliary[content['id']])
            else:
                matches = [k for k in auxiliary if congress == re.search('^[0-9]+', k).group(0) and
                           chamber in k and id_val == re.search('[0-9]+$', k).group(0)]
                if len(matches) == 1:
                    content.update(auxiliary[matches[0]])

                else:
                    content.update({k: None for k in auxiliary[auxiliary.keys()[0]]})

            with open(file_name, 'wb') as f:
                f.write(json.dumps(content))

    def _retrieve_auxiliary(self):
        return {}


class UnitedStates(_AuxiliaryBase):
    def _retrieve_auxiliary(self):
        import re
        import csv
        from datetime import datetime
        from datetime import timedelta
        from itertools import chain

        def get_id(base):
            congress = re.search('^[0-9]+', base).group(0)
            if congress[-1] == '1':
                ending = 'st'
            elif congress[-1] == '2':
                ending = 'nd'
            elif congress[-1] == '3':
                ending = 'rd'
            else:
                ending = 'th'

            chamber_regex = re.search('H', base)
            if chamber_regex:
                chamber = 'house'
                if 'RES' in base:
                    bill_type = 'joint-resolution'
                else:
                    bill_type = 'bill'

            else:
                chamber = 'senate'
                if 'R' in base:
                    bill_type = 'joint-resolution'
                else:
                    bill_type = 'bill'

            bill_id = re.search('[0-9]+$', base).group(0)

            full_id = '{0}{1}-congress_{2}-{3}_{4}'.format(congress, ending, chamber, bill_type, bill_id)

            return full_id

        def format_aux(aux_row):
            commemorative = aux_row[6]
            topic = aux_row[10]

            date = aux_row[9]
            if '/' in date:
                date = datetime.strptime(date, '%m/%d/%Y')
            else:
                date = date[2:]
                date = datetime.strptime(date, '%d-%m-%y')

            if date in unified:
                control = 'unified'
            elif date in divided:
                control = 'divided'
            else:
                print 'bad date!'
                raise

            member_id = re.search('^[0-9]+', row[46]).group(0)
            congress = re.search('^[0-9]+', row[1]).group(0)

            dw_nom = row[37]

            if int(congress) >= 103 and (member_id in house_aux[congress] or member_id in senate_aux[congress]):
                if member_id in house_aux[congress]:
                    member_entry = house_aux[congress][member_id]
                    party = member_entry['party']
                    # majority_member = member_entry['majority']
                    if (party == '200' and date not in house_dem_majority) or \
                       (party != '200' and date in house_dem_majority):

                        majority_member = '1'
                    else:
                        majority_member = '0'

                else:
                    member_entry = senate_aux[congress][member_id]
                    party = member_entry['party']
                    # majority_member = member_entry['majority']
                    if (party == '200' and date not in senate_dem_majority) or \
                            (party != '200' and date in senate_dem_majority):

                        majority_member = '1'
                    else:
                        majority_member = '0'

            else:
                majority_member = row[45]
                party = row[51]

            if (party == '200' and date not in dem_president) or (party != '200' and date in dem_president):
                president_party = '1'
            else:
                president_party = '0'

            return {'sponsor_party': party, 'sponsor_majority': majority_member, 'dw': dw_nom, 'control': control,
                    'topic': topic, 'commemorative': commemorative, 'president_party': president_party,
                    'date': date.strftime('%m/%d/%Y')}

        def get_year(x):
            return [datetime.strptime('01/01/' + x, '%d/%m/%Y') + timedelta(y)
                    for y in range(0, 365)]

        bills_aux = []
        senate_aux = {}
        house_aux = {}

        divided = list(chain(*[get_year(year) for year in ['1973', '1974', '1975', '1976', '1981', '1982', '1983',
                                                           '1984', '1985', '1986', '1987', '1988', '1989', '1990',
                                                           '1991', '1992', '1995', '1996', '1997', '1998', '1999',
                                                           '2000', '2001', '2002', '2007', '2008', '2011', '2012',
                                                           '2013', '2014', '2015', '2016']]))

        unified = list(chain(*[get_year(year) for year in ['1977', '1978', '1979', '1980', '1993', '1994', '2003',
                                                           '2004', '2005', '2006', '2009', '2010']]))

        house_dem_majority = list(chain(*[get_year(year) for year in ['1973', '1974', '1975', '1976', '1977', '1978',
                                                                      '1979', '1980', '1981', '1982', '1983', '1984',
                                                                      '1985', '1986', '1987', '1988', '1989', '1990',
                                                                      '1991', '1992', '1993', '1994', '2007', '2008',
                                                                      '2009', '2010']]))
        senate_dem_majority = list(chain(*[get_year(year) for year in ['1973', '1974', '1975', '1976', '1977', '1978',
                                                                       '1979', '1980', '1987', '1988', '1989', '1990',
                                                                       '1991', '1992', '1993', '1994', '2001', '2007',
                                                                       '2008', '2009', '2010', '2011', '2012', '2013',
                                                                       '2014']]))

        dem_president = list(chain(*[get_year(year) for year in ['1977', '1978', '1979', '1980', '1993', '1994', '1995',
                                                                 '1996', '1997', '1998', '1999', '2000', '2009', '2010',
                                                                 '2011', '2012', '2013', '2014', '2015', '2016']]))

        # remapping certain legislator IDs

        for file_name in self.aux_files:
            with open(file_name, 'rb') as f:
                if 'bills' in file_name:
                    bills_aux = list(csv.reader(f, delimiter='\t'))[1:]
                elif 'senate' in file_name:
                    senate_aux_list = list(csv.reader(f))[1:]
                    for row in senate_aux_list:
                        if row[0] in senate_aux:
                            senate_aux[row[0]][row[2]] = {'party': row[8]}
                        else:
                            senate_aux[row[0]] = {row[2]: {'party': row[8]}}

                elif 'house' in file_name:
                    house_aux_list = list(csv.reader(f))[1:]
                    for row in house_aux_list:
                        if row[0] in house_aux:
                            house_aux[row[0]][row[2]] = {'party': row[8]}
                        else:
                            house_aux[row[0]] = {row[2]: {'party': row[8]}}

        aux_out = {}
        for row in bills_aux:
            base_id = row[1]

            if re.search('[0-9]+\-[A-Z]+\-[0-9]+', base_id) and re.search('[0-9]+\-[0-9]+\-[0-9]+', row[46]):
                id_val = get_id(base_id)
                aux_data = format_aux(row)
                aux_out[id_val] = aux_data

        return aux_out
