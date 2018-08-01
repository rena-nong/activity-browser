# -*- coding: utf-8 -*-
import brightway2 as bw
from PyQt5 import QtCore, QtWidgets

from ..tables import ExchangeTable
from ..widgets import ActivityDataGrid, DetailsGroupBox
from ...signals import signals

class ActivityTab(QtWidgets.QWidget):
    """The data relating to Brightway activities can be viewed and edited through this panel interface
    The interface is a GUI representation of the standard activity data format as determined by Brightway
    This is necessitated as AB does not save its own data structures to disk
    Data format documentation is under the heading "The schema for an LCI dataset in voluptuous is:" at this link:
    https://docs.brightwaylca.org/intro.html#database-is-a-subclass-of-datastore
    Note that all activity data are optional.
    When activities contain exchanges, some fields are required (input, type, amount)
    Each exchange has a type: production, substitution, technosphere, or biosphere
    AB does not yet support 'substitution'. Other exchange types are shown in separate columns on this interface
    Required and other common exchange data fields are hardcoded as column headers in these tables
    More detail available at: https://docs.brightwaylca.org/intro.html#exchange-data-format
    The technosphere products (first table) of the visible activity are consumed by other activities downstream
    The final table of this tab lists these 'Downstream Consumers'
    """

    def __init__(self, parent=None, activity_key=None, read_only=True, db_read_only=True):
        super(ActivityTab, self).__init__(parent)
        self.parent = parent
        self.read_only = read_only
        self.db_read_only = db_read_only
        self.activity_key=activity_key
        # checkbox for enabling editing of activity, default=read-only
        self.connect_signals()
        self.read_only_ch = QtWidgets.QCheckBox('Read-Only', parent=self)
        self.read_only_ch.setChecked(self.read_only)
        self.db_name = self.activity_key[0]
        self.read_only_ch.clicked.connect(
            lambda checked, db_name=self.db_name: self.readOnlyStateChanged(db_name=db_name, read_only=checked))

        self.activity_read_only_box_active(db_name=self.db_name, db_editable=not self.db_read_only)
        # activity-specific data as shown at the top
        self.activity_data_grid = ActivityDataGrid(read_only=self.read_only)

        # exchange data shown after the activity data which it relates to, in tables depending on exchange type
        self.production = ExchangeTable(self, tableType="products")
        self.inputs = ExchangeTable(self, tableType="technosphere")
        self.flows = ExchangeTable(self, tableType="biosphere")
        self.upstream = ExchangeTable(self, tableType="technosphere")

        self.exchange_tables = [
            (self.production, "Products:"),
            (self.inputs, "Technosphere Inputs:"),
            (self.flows, "Biosphere flows:"),
            (self.upstream, "Downstream consumers:"),
        ]

        # arrange activity data and exchange data into desired vertical layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.read_only_ch)
        layout.addWidget(self.activity_data_grid)
        for table, label in self.exchange_tables:
            layout.addWidget(DetailsGroupBox(label, table))

        self.set_exchange_tables_read_only(read_only=read_only)

        layout.addStretch()
        layout.setAlignment(QtCore.Qt.AlignTop)
        self.setLayout(layout)

        if activity_key:
            self.populate(activity_key)

    def populate(self, key):
        self.activity = bw.get_activity(key)

        self.activity_data_grid.populate(self.activity)
        # todo: add count of results for each exchange table, to label above each table
        self.production.set_queryset(key[0], self.activity.production())
        self.inputs.set_queryset(key[0], self.activity.technosphere())
        self.flows.set_queryset(key[0], self.activity.biosphere())
        self.upstream.set_queryset(key[0], self.activity.upstream(), upstream=True)

    def readOnlyStateChanged(self, db_name, read_only):
        """ When checked=False specific data fields in the tables below become editable
            When checked=True these same fields become read-only"""
        # print("ro state change (if db_name=self.db_name):", db_name, self.activity_key)
        if db_name == self.activity_key[0]:
            ActivityDataGrid.set_activity_fields_read_only(self.activity_data_grid, read_only=read_only)
            self.set_exchange_tables_read_only(read_only=read_only)
            # Don't automatically force actuivity to editable even if activity in an editable database
            # the user still ticks to choose when they want to edit a specific one
            if read_only:
                self.read_only_ch.setChecked(read_only)
            #todo: save activity RO state to settings file?

    def set_exchange_tables_read_only(self, read_only):
        self.read_only = read_only
        # the user should not be able to edit the exchange tables when read_only
        # EditTriggers turned off to prevent DoubleClick editing
        # DragDropMode set to NoDragDrop prevents exchanges dropped on the table to add
        for table, label in self.exchange_tables:
            if self.read_only:
                table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
                table.setDragDropMode(QtWidgets.QTableWidget.NoDragDrop)
            else:
                table.setEditTriggers(QtWidgets.QTableWidget.DoubleClicked)
                table.setDragDropMode(QtWidgets.QTableWidget.DropOnly)

    def activity_read_only_box_active(self, db_name, db_editable):
        """ If database is set to read-only, the read-only checkbox cannot be unchecked by user"""
        # print(db_name, db_editable)
        if db_name == self.activity_key[0]:
            self.read_only_ch.setEnabled(db_editable)

    def connect_signals(self):
        signals.activity_read_only_changed.connect(self.readOnlyStateChanged)
        signals.database_writable_enabled.connect(self.activity_read_only_box_active)