import contextlib

from selenium.webdriver.support.ui import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys


class Util(object):

    def __init__(self, driver, default_timeout=2):
        self.driver = driver
        self.timeouts = [default_timeout]
        self.driver.set_script_timeout(default_timeout)
        self._can_set_cookies = driver.name != "internet explorer"

    @property
    def can_set_cookies(self):
        """
        ``True`` if the driver we are using is able to set cookies. Bugs in
        selenium sometimes prevent this from being true.
        """
        return self._can_set_cookies

    @property
    def timeout(self):
        return self.timeouts[0]

    @contextlib.contextmanager
    def local_timeout(self, value):
        self.push_timeout(value)
        try:
            yield
        finally:
            self.pop_timeout()

    def push_timeout(self, new):
        self.timeouts[0:0] = [new]
        self.driver.set_script_timeout(new)

    def pop_timeout(self):
        if len(self.timeouts) == 1:
            raise Exception("can't pop when there is only one element on "
                            "the stack")
        # The new timeout is currently in 2nd position.
        self.driver.set_script_timeout(self.timeouts[1])
        return self.timeouts.pop(0)

    def find_element(self, locator):
        return WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located(locator))

    def find_elements(self, locator):
        return WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_all_elements_located(locator))

    def find_clickable_element(self, locator):
        return WebDriverWait(self.driver, self.timeout).until(
            EC.element_to_be_clickable(locator))

    def find_descendants_by_text_re(self, parent, re):
        """
        :param parent: The parent element into which to search.
        :type parent: :class:`selenium.webdriver.remote.webelement.WebElement`
        :param re: A regular expression in JavaScript syntax.
        :type re: :class:`str`
        :returns: The descendants whose text (as returned by
                  ``jQuery().text()``) match the regular expression.

        """

        def cond(*_):
            return self.driver.execute_script("""
            var parent = arguments[0];
            var re = new RegExp(arguments[1]);
            return jQuery(parent).find("*").filter(function () {
            return re.test(jQuery(this).text().trim());
            }).toArray();
            return ret;
            """, parent, re)

        return self.wait(cond)

    #
    # The key sending methods are here as a sort of insurance policy
    # againts possible issues with the various drivers that Selenium
    # uses.  We used to emit sequences like Ctrl-X or Shift-Q as
    # key_down, send_keys, key_up sequences. However, these sequence
    # are **really** expensive when using a remote setup. So the
    # following methods use a single send_keys instead. If this turns
    # out to be a problem eventually, we can still revers to the
    # key_down, send_keys, key_up sequence if we ever need to do this.
    #
    def ctrl_x(self, x):
        """
        Sends a character to the currently active element with Ctrl
        pressed. This method takes care of pressing and releasing
        Ctrl.
        """
        ActionChains(self.driver) \
            .send_keys([Keys.CONTROL, x, Keys.CONTROL]) \
            .perform()

    def send_keys(self, element, x):
        """
        Sends keys to the element. This method takes care of handling
        modifiers keys. To press and release a modifier key you must
        include it twice: once to press, once to release.
        """
        ActionChains(self.driver) \
            .send_keys_to_element(element, x) \
            .perform()

    def get_text_excluding_children(self, element):
        return self.driver.execute_script("""
        return jQuery(arguments[0]).contents().filter(function() {
            return this.nodeType == Node.TEXT_NODE;
        }).text();
        """, element)

    def element_screen_position(self, element):
        return self.driver.execute_script("""
        var $ = jQuery;
        var offset = $(arguments[0]).offset();
        var $document = $(document);
        offset.top -= $document.scrollTop();
        offset.left -= $document.scrollLeft();
        return offset;
        """,
                                          element)

    def element_screen_center(self, element):
        """
        :returns: The center point of the element.
        :rtype: class:`dict` with the field "left" set to the X
                coordinate and the field "top" set to the Y
                coordinate.

        """
        pos = self.element_screen_position(element)
        size = element.size
        pos["top"] += int(size["height"] / 2)
        pos["left"] += int(size["width"] / 2)
        return pos

    def visible_to_user(self, element, *ignorable):
        """
        Determines whether an element is visible to the user. A list of
        ignorable elements can be passed to this function. These would
        typically be things like invisible layers sitting atop other
        elements. This function ignores these elements by setting
        their CSS ``display`` parameter to ``none`` before checking,
        and restoring them to their initial value after checking. The
        list of ignorable elements should not contain elements that
        would disturb the position of the element to check if their
        ``display`` parameter is set to ``none``. Otherwise, the
        algorithm is likely to fail.

        :param element: The element to check.
        :type element: :class:`selenium.webdriver.remote.webelement.WebElement`
        :param ignorable: The elements that can be ignored.
        :type ignorable: :class:`list` of :strings that are jQuery selectors.

        """
        if not element.is_displayed():
            return False
        pos = self.element_screen_position(element)
        size = element.size
        window_size = self.get_window_inner_size()

        # Outside the viewport
        if (pos["top"] + size["height"] < 0 or  # above
                pos["left"] + size["width"] < 0 or  # to the left
                pos["top"] > window_size["height"] or  # below
                pos["left"] > window_size["width"]):  # to the right
            return False

        return self.driver.execute_script("""
        var el = arguments[0];
        var ignorable = arguments[1];
        var $ = jQuery;

        var old_displays = [];
        var $ignorable = $(ignorable);
        ignorable.forEach(function (x) {
            old_displays.push($(x).css("display"));
        });
        $ignorable.css("display", "none");
        try {
            var rect = el.getBoundingClientRect();
            var ret = false;

            var efp = document.elementFromPoint.bind(document);
            var at_corner;
            ret = (at_corner = efp(rect.left, rect.top) === el) ||
                   el.contains(at_corner) ||
                  (at_corner = efp(rect.left, rect.bottom) === el) ||
                   el.contains(at_corner) ||
                  (at_corner = efp(rect.right, rect.top) === el) ||
                   el.contains(at_corner) ||
                  (at_corner = efp(rect.right, rect.bottom) === el) ||
                   el.contains(at_corner);
        }
        finally {
            var ix = 0;
            ignorable.forEach(function (x) {
                $(x).css("display", old_displays[ix]);
                ix++;
            });
        }
        return ret;
        """, element, ignorable)

    def get_window_inner_size(self):
        return self.driver.execute_script("""
        return {height: window.innerHeight, width: window.innerWidth};
        """)

    def completely_visible_to_user(self, element):
        if not element.is_displayed():
            return False
        pos = self.element_screen_position(element)
        size = element.size
        window_size = self.driver.get_window_size()
        return (pos["top"] >= 0 and
                pos["left"] >= 0 and
                pos["top"] + size["height"] <= window_size["height"] and
                pos["left"] + size["width"] <= window_size["width"])

    def get_selection_text(self):
        """
        Gets the text of the current selection.

        .. note:: This function requires that ``rangy`` be installed.

        :returns: The text.
        :rtype: class:`basestring`
        """
        return self.driver.execute_script("""
        return rangy.getSelection(window).toString()
        """)

    def is_something_selected(self):
        """
        :returns: Whether something is selected.
        :rtype: class:`bool`
        """
        return self.driver.execute_script("""
        var sel = window.getSelection();
        return sel.rangeCount && !sel.getRangeAt(0).collapsed;
        """)

    def scroll_top(self, element):
        """
        Gets the top of the scrolling area of the element.

        :param element: An element on the page.
        :type element: :class:`selenium.webdriver.remote.webelement.WebElement`
        :returns: The top of the scrolling area.
        """
        return self.driver.execute_script("""
        return arguments[0].scrollTop;
        """, element)

    def window_scroll_top(self):
        """
        Gets the top of the scrolling area for ``window``.

        :returns: The top of the scrolling area.
        """
        return self.driver.execute_script("""
        return window.scrollY;
        """)

    def window_scroll_left(self):
        """
        Gets the left of the scrolling area for ``window``.

        :returns: The left of the scrolling area.
        """
        return self.driver.execute_script("""
        return window.scrollX;
        """)

    def wait(self, condition):
        """
        Waits for a condition to be true.

        :param condition: Should be a callable that operates in the
                          same way ``WebDriverWait.until`` expects.
        :returns: Whatever ``WebDriverWait.until`` returns.
        """
        return WebDriverWait(self.driver, self.timeout).until(condition)

    def wait_until_not(self, condition):
        """
        Waits for a condition to be false.

        :param condition: Should be a callable that operates in the
                          same way ``WebDriverWait.until_not`` expects.
        :returns: Whatever ``WebDriverWait.until_not`` returns.
        """
        return WebDriverWait(self.driver, self.timeout).until_not(condition)

    def get_html(self, element):
        """
        :param element: The element.
        :type element: :class:`selenium.webdriver.remote.webelement.WebElement`
        :returns: The HTML of an element.
        :rtype: :class:`str`
        """
        return self.driver.execute_script("""
        return arguments[0].outerHTML;
        """, element)

    def number_of_siblings(self, element):
        """
        :param element: The element.
        :type element: :class:`selenium.webdriver.remote.webelement.WebElement`
        :returns: The number of siblings.
        :rtype: :class:`int`
        """
        return self.driver.execute_script("""
        return arguments[0].parentNode.childNodes.length;
        """, element)

    def assert_same(self, first, second):
        """
        Compares two items for identity. The items can be either single
        values or lists of values. When comparing lists, identity
        obtains when the two lists have the same number of elements
        and that the element at position in one list is identical to
        the element at the same position in the other list.

        This method is meant to be used for comparing lists of DOM
        notes. It would also work with lists of booleans, integers,
        and similar primitive types, but is pointless in such
        cases. Also note that this method cannot meaningfully compare
        lists of lists or lists of dictionaries since the objects that
        would be part of the list would be created anew by Selenium's
        marshalling procedure. Hence, in these cases, the assertion
        would always fail.

        :param first: The first item to compare.
        :type first:
                     :class:`selenium.webdriver.remote.webelement.WebElement`
                     or array of
                     :class:`selenium.webdriver.remote.webelement.WebElement`.
        :param second: The second item to compare.
        :type second:
           :class:`selenium.webdriver.remote.webelement.WebElement` or
           :array of
           :class:`selenium.webdriver.remote.webelement.WebElement`.
        :raises: :class:`AssertionError` when unequal.
        """
        if not isinstance(first, list):
            first = [first]
        if not isinstance(second, list):
            second = [second]
        if not self.driver.execute_script("""
        var first = arguments[0];
        var second = arguments[1];
        if (first.length != second.length)
            return false;
        for(var i = 0; i < first.length; ++i)
            if (first[i] !== second[i])
                return false;
        return true;
        """, first, second):
            raise AssertionError("unequal")


def locations_within(a, b, tolerance):
    """
    Verifies whether two positions are the same. A tolerance value
    determines how close the two positions must be to be considered
    "same".

    The two locations must be dictionaries that have the same keys. If
    a key is pesent in one but not in the other, this is an error. The
    values must be integers or anything that can be converted to an
    integer through ``int``. (If somehow you need floating point
    precision, this is not the function for you.)

    Do not rely on this function to determine whether two object have
    the same keys. If the function finds the locations to be within
    tolerances, then the two objects have the same keys. Otherwise,
    you cannot infer anything regarding the keys because the function
    will return as soon as it knows that the two locations are **not**
    within tolerance.

    :param a: First position.
    :type a: :class:`dict`
    :param b: Second position.
    :type b: :class:`dict`
    :param tolerance: The tolerance within which the two positions
                      must be.
    :return: An empty string if the comparison is successful. Otherwise,
             the string contains a description of the differences.
    :rtype: :class:`str`
    :raises ValueError: When a key is present in one object but not
                        the other.
    """
    ret = ''
    # Clone b so that we can destroy it.
    b = dict(b)

    for (key, value) in a.items():
        if key not in b:
            raise ValueError("b does not have the key: " + key)
        if abs(int(value) - int(b[key])) > tolerance:
            ret += 'key {0} differs: {1} {2}'.format(key, int(value),
                                                     int(b[key]))
        del b[key]

    if b:
        raise ValueError("keys in b not seen in a: " + ", ".join(b.keys()))

    return ret
