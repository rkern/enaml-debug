from collections import defaultdict
import os
import sys
import types

from enable.api import (AbstractOverlay, ColorTrait,
    Component as EnableComponent, Container as EnableContainer, LineStyle,
    transparent_color)
from kiva.constants import FILL, STROKE
from traits.api import (Any, Bool, Float, HasTraits, Instance, List, Property,
    NO_COMPARE, on_trait_change)

from casuarius import medium
from enaml import imports
from enaml.components.constraints_widget import ConstraintsWidget
from enaml.components.container import Container
from enaml.core.enaml_compiler import EnamlCompiler
from enaml.core.parser import parse
from enaml.core.trait_types import EnamlEvent
from enaml.item_models.abstract_item_model import (ALIGN_LEFT, ALIGN_RIGHT,
    ALIGN_VCENTER, AbstractTableModel)
from enaml.layout.constraints_layout import ConstraintsLayout
from enaml.styling.font import Font


# Use a monospaced font for the tables.
TABLE_FONT = Font('Courier New', point_size=10, family_hint='monospace')


class DebugLayout(HasTraits, ConstraintsLayout):
    """ Sublass ConstraintsLayout to keep around the constraint list and
    to let us inject our own callback inside the layout edit cycle.

    """
    current_constraints = List(comparison_mode=NO_COMPARE)
    layout_event = EnamlEvent()

    def initialize(self, constraints):
        self.current_constraints = constraints
        super(DebugLayout, self).initialize(constraints)

    def layout(self, cb, width, height, size, strength=medium, weight=1.0):
        def f():
            cb()
            self.layout_event()

        super(DebugLayout, self).layout(f, width, height, size, strength, weight)


class DebugModel(HasTraits):
    """ Hold the component hierarchy data.

    """

    # The root Container.
    root = Instance(Container)

    # The full list of components.
    components = List()

    # The full list of constraints.
    constraints = List(comparison_mode=NO_COMPARE)

    # The components that are selected.
    selected_components = List()

    # The constraints that are selected.
    selected_constraints = List(comparison_mode=NO_COMPARE)

    # Notify that the hierarchy has changed.
    hierarchy_changed = EnamlEvent()

    # The layout manager for the root.
    layout_manager = Instance(DebugLayout)


    @on_trait_change('root.children*')
    def _update_components(self):
        if self.root is None:
            self.components = []
        else:
            self.components = list(traverse_layout(self.root))
        self.hierarchy_changed()

    def _root_changed(self, new):
        if new is not None and type(new) is not DebugContainer:
            debugize_container(new)
            self.layout_manager = new.layout_manager

    @on_trait_change('layout_manager.current_constraints')
    def _new_constraints(self):
        if self.layout_manager is not None:
            self.constraints = self.layout_manager.current_constraints
        else:
            self.constraints = []


class Coords(HasTraits):
    """ Simple holder of box-related data.

    """
    top = Float()
    left = Float()
    width = Float()
    height = Float()

    v_center = Property()
    _v_center = Any()
    def _get_v_center(self):
        if self._v_center is None:
            return self.top + 0.5 * self.height
        else:
            return self._v_center
    def _set_v_center(self, value):
        self._v_center = value

    h_center = Property()
    _h_center = Any()
    def _get_h_center(self):
        if self._h_center is None:
            return self.left + 0.5 * self.width
        else:
            return self._h_center
    def _set_h_center(self, value):
        self._h_center = value


class Box(EnableComponent):
    """ Draw a highlightable box representing the geometry of an Enaml
    component.

    """

    enaml = Instance(ConstraintsWidget)
    highlighted = Bool(False)

    normal_fill_color = ColorTrait('transparent')
    highlight_fill_color = ColorTrait('red')
    fill_color = Property(depends_on=['highlighted', 'normal_fill_color',
        'highlight_border_color'])
    def _get_fill_color(self):
        if self.highlighted:
            return self.highlight_fill_color_
        else:
            return self.normal_fill_color_

    normal_border_color = ColorTrait('lightgray')
    highlight_border_color = ColorTrait('black')
    border_color = Property(depends_on=['highlighted', 'normal_border_color',
        'highlight_border_color'])
    def _get_border_color(self):
        if self.highlighted:
            return self.highlight_border_color_
        else:
            return self.normal_border_color_

    coords = Instance(Coords, args=())

    def update_from_enaml(self):
        """ Update the geometry from the Enaml component.

        """
        if self.enaml.abstract_obj is not None and self.enaml.abstract_obj.widget is not None:
            coords = self.coords
            coords.left = self.enaml.left.value
            coords.top = self.enaml.top.value
            coords.width = self.enaml.width.value
            coords.height = self.enaml.height.value
            self.position = [coords.left, self.container.height - coords.top - coords.height]
            self.bounds = [coords.width, coords.height]
            coords.v_center = self.enaml.v_center.value
            coords.h_center = self.enaml.h_center.value
            if hasattr(self.enaml, 'midline'):
                coords.midline = self.enaml.midline.value
            if hasattr(self.enaml, 'padding_top'):
                coords.padding_top = self.enaml.padding_top.value
                coords.padding_left = self.enaml.padding_left.value
                coords.padding_right = self.enaml.padding_right.value
                coords.padding_bottom = self.enaml.padding_bottom.value

    def _draw_mainlayer(self, gc, view_bounds=None, mode="default"):
        """ Draw the box background in a specified graphics context.

        """
        # Set up all the control variables for quick access:
        coords = self.coords
        x, y = coords.left, coords.top
        dx, dy = coords.width, coords.height

        with gc:
            gc.translate_ctm(0.0, self.container.height)
            gc.scale_ctm(1.0, -1.0)
            # Fill the background region (if required);
            color = self.fill_color
            if color is not transparent_color:
                gc.set_fill_color(color)
                gc.draw_rect((x, y, dx, dy), FILL)

            # Draw the border (if required):
            border_color = self.border_color
            if border_color is not transparent_color:
                gc.set_stroke_color(border_color)
                gc.set_line_width(1)
                gc.draw_rect((x, y, dx, dy), STROKE)
    
            # Draw the center lines, padding and midlines only if highlighted.
            if self.highlighted and border_color is not transparent_color:
                gc.set_stroke_color(border_color)
                gc.set_alpha(0.5)
                gc.set_line_width(1)
                gc.begin_path()
                gc.move_to(x, coords.v_center)
                gc.line_to(x+dx, coords.v_center)
                gc.move_to(coords.h_center, y)
                gc.line_to(coords.h_center, y+dy)
                if hasattr(coords, 'midline'):
                    gc.move_to(coords.midline, y)
                    gc.line_to(coords.midline, y+dy)
                gc.stroke_path()
                if hasattr(coords, 'padding_top'):
                    gc.draw_rect((x+coords.padding_left, y+coords.padding_top,
                        dx-coords.padding_left-coords.padding_right,
                        dy-coords.padding_top-coords.padding_bottom), STROKE)


class ViewOutlines(EnableContainer):
    """ Enable component that shows Boxes for Enaml components.

    """

    model = Instance(DebugModel)

    # No padding.
    padding_left = 0
    padding_right = 0
    padding_top = 0
    padding_bottom = 0

    @on_trait_change('model.hierarchy_changed')
    def _new_components(self):
        self.remove(*self._components)
        if self.model is not None:
            for component in self.model.components:
                box = Box(enaml=component)
                self.add(box)

    @on_trait_change('model:layout_manager:layout_event')
    def update_from_enaml(self):
        """ Update each of the Boxes from their Enaml geometry.

        """
        for box in self.components:
            box.update_from_enaml()
        self.request_redraw()

    @on_trait_change('model:selected_components')
    def highlight(self):
        """ Highlight the selected Enaml components.

        """
        for box in self.components:
            box.highlighted = (box.enaml in self.model.selected_components)
        self.request_redraw()


class ConstraintsOverlay(AbstractOverlay):
    """ Highlight the selected constraints on the outline view.

    """

    model = Instance(DebugModel)

    # Map from box name to Coords.
    boxes = Any()

    # Style options for the lines.
    term_color = ColorTrait('lightblue')
    term_line_style = LineStyle('solid')

    @on_trait_change('model:layout_manager:layout_event')
    def update_from_enaml(self):
        """ Update the constraints from Enaml.

        """
        self.boxes = defaultdict(Coords)
        layout_mgr = getattr(self.model, 'layout_manager', None)
        if layout_mgr is not None:
            for constraint in layout_mgr.current_constraints:
                for expr in (constraint.lhs, constraint.rhs):
                    for term in expr.terms:
                        name, attr = self.split_var_name(term.var.name)
                        setattr(self.boxes[name], attr, term.var.value)
        self.request_redraw()

    @on_trait_change('model.selected_constraints')
    def _selected_constraints_changed(self):
        self.request_redraw()

    def split_var_name(self, var_name):
        attr, class_name, hexid = var_name.rsplit('_', 2)
        name = '{}_{}'.format(class_name, hexid)
        return name, attr

    def overlay(self, other_component, gc, view_bounds=None, mode="normal"):
        """ Draws this component overlaid on another component.

        """
        if self.model is None:
            return
        with gc:
            gc.translate_ctm(0.0, other_component.height)
            gc.scale_ctm(1.0, -1.0)
            gc.set_stroke_color(self.term_color_)
            gc.set_line_dash(self.term_line_style_)
            gc.set_line_width(3)
            term_attrs = set()
            for constraint in self.model.selected_constraints:
                for expr in (constraint.lhs, constraint.rhs):
                    for term in expr.terms:
                        term_attrs.add(self.split_var_name(term.var.name))
            for name, attr in sorted(term_attrs):
                box = self.boxes[name]
                if attr == 'top':
                    self.hline(gc, box.left, box.top, box.width)
                elif attr == 'left':
                    self.vline(gc, box.left, box.top, box.height)
                elif attr == 'width':
                    self.hline(gc, box.left, box.v_center, box.width)
                elif attr == 'height':
                    self.vline(gc, box.h_center, box.top, box.height)
                elif attr == 'midline':
                    self.vline(gc, box.midline, box.top, box.height)
                elif attr == 'padding_top':
                    self.vline(gc, box.h_center, box.top, box.padding_top)
                elif attr == 'padding_bottom':
                    self.vline(gc, box.h_center, box.top+box.height, -box.padding_bottom)
                elif attr == 'padding_left':
                    self.hline(gc, box.left, box.v_center, box.padding_left)
                elif attr == 'padding_right':
                    self.hline(gc, box.left+box.width, box.v_center, -box.padding_right)
                elif attr == 'bottom':
                    self.hline(gc, box.left, box.bottom, box.right - box.left)
                elif attr == 'right':
                    self.vline(gc, box.right, box.top, box.bottom - box.top)
                gc.stroke_path()

    def vline(self, gc, x, y0, length):
        """ Draw a vertical line.

        """
        gc.move_to(x, y0)
        gc.line_to(x, y0+length)

    def hline(self, gc, x0, y, length):
        """ Draw a horizontal line.

        """
        gc.move_to(x0, y)
        gc.line_to(x0+length, y)


class ComponentModel(AbstractTableModel):
    """ Table model for showing the tree of components.

    """

    def __init__(self, debug_model):
        self.debug_model = debug_model

        self.columns = [
            ('Name', 'name'),
            ('ID', 'id'),
            ('Left', 'left'),
            ('Top', 'top'),
            ('Width', 'width'),
            ('Height', 'height'),
        ]
        self._data = []
        self.update()
        self.debug_model.on_trait_change(self.update, 'layout_manager:layout_event')

    #### AbstractTableModel interface ########################################

    def column_count(self, parent=None):
        return len(self.columns)

    def row_count(self, parent=None):
        return len(self.debug_model.components)

    def data(self, index):
        return self._data[index.row][index.column]

    def alignment(self, index):
        if index.column < 2:
            return ALIGN_LEFT | ALIGN_VCENTER
        else:
            return ALIGN_RIGHT | ALIGN_VCENTER

    def horizontal_header_data(self, section):
        return self.columns[section][0]

    def font(self, index):
        return TABLE_FONT

    #### ComponentModel interface #############################################

    def update(self):
        """ Redraw everything.

        """
        self.begin_reset_model()
        self._data = []
        for component in self.debug_model.components:
            self._data.append((
                self._get_name(component),
                self._get_id(component),
                self._get_left(component),
                self._get_top(component),
                self._get_width(component),
                self._get_height(component),
            ))

        self.end_reset_model()

    def _get_name(self, component):
        if component is self.debug_model.components[0]:
            nancestors = 0
        else:
            nancestors = len(list(component.traverse_ancestors(self.debug_model.components[0])))+1
        return u'{0}{1}'.format(u'\u2003'*nancestors, type(component).__name__)

    def _get_id(self, component):
        return u'{0:x}'.format(id(component))

    def _get_top(self, component):
        return unicode(int(round(component.top.value)))

    def _get_left(self, component):
        return unicode(int(round(component.left.value)))

    def _get_width(self, component):
        return unicode(int(round(component.width.value)))

    def _get_height(self, component):
        return unicode(int(round(component.height.value)))


class ConstraintsModel(AbstractTableModel):
    """ Table model for viewing the constraints.

    """

    def __init__(self, debug_model):
        self.debug_model = debug_model
        self.debug_model.on_trait_change(self.update, 'constraints')
        self.debug_model.on_trait_change(self.update, 'layout_manager:layout_event')
        self.debug_model.on_trait_change(self.filter, 'selected_components')

        self._data = []
        self._filter_ids = ()
        self.filtered_constraints = []
        self.update()

    #### AbstractTableModel interface ########################################

    def row_count(self, parent=None):
        if parent is not None:
            return 0
        else:
            return len(self._data)

    def column_count(self, parent=None):
        return 4

    def horizontal_header_data(self, section):
        return ('Constraint', 'Error', 'Strength', 'Weight')[section]

    def data(self, index):
        return self._data[index.row][index.column]

    def alignment(self, index):
        if index.column in (0, 2):
            return ALIGN_LEFT | ALIGN_VCENTER
        else:
            return ALIGN_RIGHT | ALIGN_VCENTER

    def font(self, index):
        return TABLE_FONT

    #### ConstraintsModel interface ###########################################

    def update(self):
        """ Update all of the data.

        """
        self.begin_reset_model()
        if self._filter_ids:
            self.filtered_constraints = []
            for cn in self.debug_model.constraints:
                for term in cn.lhs.terms + cn.rhs.terms:
                    if term.var.name.endswith(self._filter_ids):
                        self.filtered_constraints.append(cn)
                        break
        else:
            self.filtered_constraints = self.debug_model.constraints
        self._data = [
            (unicode(cn),
             u'{0:.6g}'.format(cn.error) if cn.error > 1e-6 else u'0',
             unicode(cn.strength.name),
             unicode(cn.weight),
            )
            for cn in self.filtered_constraints
        ]
        self.end_reset_model()

    def filter(self):
        """ Filter the constraint list to only show the constraints
        belonging to the given components.

        """
        self._filter_ids = tuple('_{0:x}'.format(id(c))
            for c in self.debug_model.selected_components)
        self.update()


class DebugContainer(Container):
    """ Make sure the Container under test does not transfer its
    ownership to the enaml-debug UI.

    """

    def transfer_layout_ownership(self, owner):
        return False


def debugize_container(container):
    """ Install the debugging hooks for a given Container.

    """
    assert type(container) is Container
    container.__class__ = DebugContainer
    container._layout_owner = None
    container.add_trait('layout_manager', Instance(DebugLayout, args=()))
    container.hug = ('weak', 'weak')
    container.initialize_layout()


def traverse_layout(root):
    """ Traverse the laid out components starting with the root container.

    """
    yield root
    for child in root.constraints_children:
        if isinstance(child, Container) and child.transfer_layout_ownership(root):
            for c in traverse_layout(child):
                yield c
        elif isinstance(child, ConstraintsWidget):
            yield child


def read_component(enaml_file, requested='Main'):
    """ Read a component from an .enaml file.

    Parameters
    ----------
    enaml_file : str
        The name of the .enaml file.
    requested : str, optional
        The name of the MainWindow holding the root Container.

    Returns
    -------
    factory : callable
        The factory for the MainWindow, usually a MainWindow
        EnamlDefinition.
    module : module
        The module object from the .enaml file itself. Keep this alive
        at least until after the component gets constructed.

    Raises
    ------
    NameError if the requested component does not exist in the module.
    """
    with open(enaml_file) as f:
        enaml_code = f.read()

    # Parse and compile the Enaml source into a code object
    ast = parse(enaml_code, filename=enaml_file)
    code = EnamlCompiler.compile(ast, enaml_file)

    # Create a proper module in which to execute the compiled code so
    # that exceptions get reported with better meaning
    module = types.ModuleType('__main__')
    module.__file__ = enaml_file
    ns = module.__dict__

    old_path = sys.path[:]
    sys.path.insert(0, os.path.dirname(enaml_file))
    with imports():
        exec code in ns
    sys.path[:] = old_path

    if requested in ns:
        factory = ns[requested]
    else:
        msg = "Could not find component {0!r}".format(requested)
        raise NameError(msg)

    return factory, module


