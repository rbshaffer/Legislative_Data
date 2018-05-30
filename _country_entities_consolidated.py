class _EntityBase:
    def __init__(self, load_lstm):
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
