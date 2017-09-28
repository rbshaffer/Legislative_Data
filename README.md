# Legislative_Data

Scraping, parsing, and entity/relation extraction tools for texts enacted legislation. Currently focused on the US (via [congress.gov](https://www.congress.gov/)), the UK ([legislation.gov.uk](http://www.legislation.gov.uk/)), Australia ([legislation.gov.au](https://www.legislation.gov.au)), and Canada ([parl.gc.ca](http://www.parl.gc.ca)). Under construction, so check back for updates!

## Setup and dependencies
Currently, this repository is only tested for Python 2. Besides base Python, the ``Legislative_Data`` library also relies on [Selenium](http://selenium-python.readthedocs.io/) (for webscraping), [NLTK](http://www.nltk.org/) (for entity extraction), [igraph](http://igraph.org/python/)/[NetworkX](https://networkx.github.io/) (for network calculations and visualization),  and [wikipedia](https://pypi.python.org/pypi/wikipedia/). Parsing and entity extraction functions are currently implemented for US legislation only, and further rely on [constitute_tools](https://github.com/rbshaffer/constitute_tools). 

## Basic usage
Most library functions are wrapped through the ``collector.DataManager`` class. Initialize the class with a working directory as follows:

```
>> from collector import DataManager
>> manager = DataManager('/path/to/working_directory')
```

Library functions can be accessed through various wrapper functions:

```
>> manager.update_data() # run the scrapers
>> manager.append_parsed() # parse scraped data
>> manager.append_auxiliary() # add auxiliary metadata from outside sources
>> manager.extract_entites(write=True) # extract entities from parsed data, and optionally write to disk
```

As mentioned earlier, various subcomponents of these functions are under construction. Depending on build state, you may need to comment out some country-level parsers for wrappers to run without error. Please message me if you have any questions!

## Parsing and entity extraction
### Overview
Currently, relations in ``Legislative_Data`` are defined using a co-mention approach. In other words, edges are drawn between extracted entities that co-occur within a given unit of analysis. In the United States, for example, the natural unit of analysis for legislative texts is the *section* (as articulated in the [Office of Law Revision Counsel's](http://uscode.house.gov/detailed_guide.xhtml) guidelines). As a result, splitting legislation into appropriate units of analysis (and cleaning extraneous text) is a critical step for the ``Legislative_Data`` library.

The parsing functions in ``Legislative_Data`` rely on the parser implemented in [constitute_tools](https://github.com/rbshaffer/constitute_tools) to parse legislation into units of analysis, which is called and applied through the ``_country_parsers_annual._CountryBase`` class (inherited by country-specific classes in ``_country_parsers_annual``). This parser cleans extraneous text, chunks documents into units of analysis (e.g. *sections* in the US case), and outputs a flat (csv-like) representation. This parsed text is then used in the entity extraction functions contained in ``_country_entities_annual._EntityBase``.  

### Customization
If the included parser is not appropriate for your application, you can input your own pre-segmented texts to the entity extraction tool as follows:

```
>> from _country_entities_annual import _EntityBase as entity_manager
>> chunks = ['We the People...', 'All legislative Powers...', ...] # format parsed text as list of strings
>> manager = entity_manager(None) # null argument in place of parsed text
>> manager.chunks = parsed
>> edges = manager.do_entity_extraction()
```
This process saves a dictionary to ``edges``, which can then be saved to disk or manipulated. Here, ``chunks`` represents a single document; to process multiple documents, wrap this piece of code in a loop.
