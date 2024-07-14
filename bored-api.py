"""
:file: pyapi.py

:date: 2024/07/14
:author: Bryan Gillis

Executable python script which displays a QT widget to allow API queries from the user.
"""

import json
import os
import requests
import subprocess
import sys
import tempfile

from PySide6 import QtCore, QtWidgets

BORED_API_URL = "http://bored.api.lewagon.com/api/activity/"

class BoredApiWidget(QtWidgets.QWidget):
    """A Qt-based which which when shown will provide an interface to make API calls to Bored API.
    """
    def __init__(self):
        super().__init__()

        # Use a two-panel layout, with input on left and output on right
        self.layout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout(self)

        self.input_layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.input_layout)
        self.output_layout = QtWidgets.QFormLayout()
        self.layout.addLayout(self.output_layout)

        # Start with the input layout on the left, and add sub-layouts to it for each query type

        # Add an option to query for a random entry
        self.random_layout = QtWidgets.QFormLayout()
        self.input_layout.addLayout(self.random_layout)

        self.random_desc_label = QtWidgets.QLabel("Option 1: Query for random entry")
        self.random_layout.addWidget(self.random_desc_label)

        self.random_button = QtWidgets.QPushButton("Query random")
        self.random_button.clicked.connect(self.query_random)
        self.random_layout.addWidget(self.random_button)

        # Add an option to query by key
        self.key_input_layout = QtWidgets.QFormLayout()
        self.input_layout.addLayout(self.key_input_layout)

        self.key_input_desc_label = QtWidgets.QLabel("Option 2: Query by key")
        self.key_input_layout.addWidget(self.key_input_desc_label)

        self.key_input_label = QtWidgets.QLabel("Key:")
        self.key_input_field = QtWidgets.QLineEdit()
        self.key_input_layout.addRow(self.key_input_label, self.key_input_field)

        self.key_input_button = QtWidgets.QPushButton("Query by key")
        self.key_input_button.clicked.connect(self.query_key)
        self.key_input_layout.addWidget(self.key_input_button)

        # Now add an option to query by multiple parameters
        self.multi_input_layout = QtWidgets.QFormLayout()
        self.input_layout.addLayout(self.multi_input_layout)

        self.multi_input_desc_label = QtWidgets.QLabel("Option 3: Query by multiple parameters")
        self.multi_input_layout.addWidget(self.multi_input_desc_label)

        self.d_multi_input_labels = {}
        self.d_multi_input_fields = {}
        self.d_multi_input_min_fields = {}
        self.d_multi_input_max_fields = {}

        self._add_param_entry("type", allow_range=False)
        self._add_param_entry("participants")
        self._add_param_entry("price")
        self._add_param_entry("accessibility")

        self.multi_input_button = QtWidgets.QPushButton("Query by params")
        self.multi_input_button.clicked.connect(self.query_multi)
        self.multi_input_layout.addWidget(self.multi_input_button)

        # Add a button to clear text entry
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear)
        self.input_layout.addWidget(self.clear_button)

        # On the right, we'll add the query output when it's generated, but not yet

        # Add a button at the end to quit, in case the user doesn't realize they need to close the
        # window to do so
        self.quit_button = QtWidgets.QPushButton("Quit")
        self.quit_button.clicked.connect(self.close)
        self.input_layout.addWidget(self.quit_button)

    def _add_param_entry(self, input_name, allow_range=True):
        """Add entry rows for a parameter to query. If allow_range==True, this adds both a row for exact entry
        and a row for range entry.
        """

        exact_label = QtWidgets.QLabel(f"{input_name.capitalize()} (exact):")
        self.d_multi_input_fields[input_name] = QtWidgets.QLineEdit()
        self.multi_input_layout.addRow(exact_label, self.d_multi_input_fields[input_name])

        range_layout = QtWidgets.QHBoxLayout()

        range_label = QtWidgets.QLabel(f"{input_name.capitalize()} (range):")

        self.d_multi_input_min_fields[input_name] = QtWidgets.QLineEdit()
        self.d_multi_input_max_fields[input_name] = QtWidgets.QLineEdit()

        range_layout.addWidget(self.d_multi_input_min_fields[input_name])
        range_layout.addWidget(QtWidgets.QLabel(" to "))
        range_layout.addWidget(self.d_multi_input_max_fields[input_name])

        if allow_range:
          # We only make the input visible if we allow a range entry. It's still there
          # but hidden if we don't, to simplify checks that assume it might exist
          self.multi_input_layout.addRow(range_label, range_layout)


    def _clear(self):
        """Clears all text entry fields in the widget.
        """

        self.key_input_field.setText("")

        for input_name in self.d_multi_input_fields:
            self.d_multi_input_fields[input_name].setText("")
            self.d_multi_input_min_fields[input_name].setText("")
            self.d_multi_input_max_fields[input_name].setText("")


    def _cleanup(self):
        """Clean up any previous test results from the widget. Note that this isn't a full implementation which can
        clean up arbitrary layouts and widgets, which would necessarily be recursive. This goes only to the depth
        necessary to clean up what exists in this widget.
        """

        # Clean up any prior results
        while self.output_layout.count():
            child = self.output_layout.takeAt(0)
            child_widget = child.widget()
            if child_widget is not None:
                child_widget.deleteLater()
            else:
                while child.count():
                    child_child = child.takeAt(0)
                    child_child_widget = child_child.widget()
                    if child_child_widget is not None:
                        child_child_widget.deleteLater()


    def _display_error(self, message):
        """Display an error in the right panel, adding it to the bottom of anything else that may
        already be present.
        """
        error_label = QtWidgets.QLabel(f"<span style='color:red;'>ERROR: {message}</span>")
        self.output_layout.addWidget(error_label)
        

    @QtCore.Slot()
    def query_random(self):
        """Method called when the query-by-random button is pressed, to send a  query to Bored API requesting a random
        entry.
        """

        self._cleanup()
        self._query(f"{BORED_API_URL}")
        

    @QtCore.Slot()
    def query_key(self):
        """Method called when the query-by-key button is pressed, to send a key query to Bored API.
        """

        self._cleanup()

        # Get the key value to query by
        key = self.key_input_field.text()

        # Check for no key provided, and output an error if so
        if not key:
            self._display_error("No key provided")
            return
        
        # Call the query method with a key query
        self._query(f"{BORED_API_URL}?key={key}")
        

    @QtCore.Slot()
    def query_multi(self):
        """Method called when the query-by-params button is pressed, to send a complicated query to Bored
        API.
        """

        self._cleanup()

        # We'll construct the query piece-by-piece from what values are present
        query_tail = ""

        for input_name in self.d_multi_input_fields:
            
            # First, check for exact value text, and only use it if it's present
            value = self.d_multi_input_fields[input_name].text()
            if value:
                query_tail += f"{input_name}={value}&"
                continue
            
            # Check for min and max value, and use them if they're present
            min_value = self.d_multi_input_min_fields[input_name].text()
            if min_value:
                query_tail += f"min{input_name}={min_value}&"
            max_value = self.d_multi_input_max_fields[input_name].text()
            if max_value:
                query_tail += f"max{input_name}={max_value}&"

        # Send the completed query now
        self._query(f"{BORED_API_URL}?{query_tail}")



    def _query(self, query):
        """Call a query to Bored API and output the results.
        """

        response = requests.get(query)

        # Check if response was successful
        if response.status_code != 200:
            self._display_error(f"API request failed: {response.status_code}")
            return
        
        d_response = response.json()

        # Check if the API returned an error
        error_message = d_response.get("error")
        if error_message:
            self._display_error(f"API request returned error: {error_message}")
            return
        
        # Output the full results to the right panel
        for key, value in d_response.items():
            self.output_layout.addRow(QtWidgets.QLabel(f"{key}:"),
                                      QtWidgets.QLabel(f"{value}"))
            
            

if __name__ == "__main__":

    app = QtWidgets.QApplication([])

    widget = BoredApiWidget()
    widget.show()

    sys.exit(app.exec())