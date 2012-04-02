#------------------------------------------------------------------------------
#  Copyright (c) 2011, Enthought, Inc.
#  All rights reserved.
#------------------------------------------------------------------------------
""" Command-line tool to debug Enaml layouts.

"""
from __future__ import absolute_import

import optparse
import sys

from enaml import imports, default_toolkit, wx_toolkit, qt_toolkit

from .debug_layout import read_component


toolkits = {
    'default': default_toolkit, 'wx': wx_toolkit, 'qt': qt_toolkit,
}


def main():
    usage = 'usage: %prog [options] enaml_file'
    parser = optparse.OptionParser(usage=usage, description=__doc__)
    parser.add_option('-c', '--component', default='Main',
                      help='The component to view')
    parser.add_option('-t', '--toolkit', default='default',
                      choices=['default', 'wx', 'qt'],
                      help='The toolkit backend to use')
    
    options, args = parser.parse_args()

    if len(args) == 0:
        print 'No .enaml file specified'
        sys.exit()
    elif len(args) > 1:
        print 'Too many files specified'
        sys.exit()
    else:
        enaml_file = args[0]

    with toolkits[options.toolkit]():
        try:
            factory, module = read_component(enaml_file, requested=options.component)
        except NameError, e:
            raise SystemExit('Error: ' + str(e))

        with imports():
            from enaml_debug.debug_ui import DebugLayoutUI

        window = DebugLayoutUI(root=factory().central_widget)
        window.show()

if __name__ == '__main__':
    main()


