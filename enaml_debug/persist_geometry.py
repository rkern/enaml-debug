import cPickle
import os

from traits.api import HasTraits, Property, Str


class PersistGeometry(HasTraits):
    """ Handle the persistence of geometry.

    """

    # The application data directory.
    datadir = Str()

    # The geometry pickle filename.
    filename = Property(Str, depends_on=['datadir'])
    def _get_filename(self):
        return os.path.join(self.datadir, 'geometry.pkl')

    def load(self):
        """ Load the persisted geometry, if any.

        """
        geometry = None
        filename = self.filename
        if os.path.exists(filename):
            try:
                with open(filename, 'rb') as f:
                    geometry = cPickle.load(f)
            except Exception:
                pass
        return geometry

    def save(self, geometry):
        """ Save the given geometry.

        """
        if not os.path.exists(self.datadir):
            os.makedirs(self.datadir)
        with open(self.filename, 'wb') as f:
            cPickle.dump(geometry, f, cPickle.HIGHEST_PROTOCOL)
