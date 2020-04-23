# -*- coding: utf-8 -*-
import brightway2 as bw
from bw2data.backends.peewee import ActivityDataset
import numpy as np
import pandas as pd

from .utils import FROM_ALL, TO_ALL, EXCHANGE_KEYS


FROM_ACT = pd.Index([
    "from activity name", "from reference product", "from location",
    "from database"
])
TO_ACT = pd.Index([
    "to activity name", "to reference product", "to location", "to database",
])
FROM_BIOS = pd.Index([
    "from activity name", "from categories", "from database"
])
TO_BIOS = pd.Index([
    "to activity name", "to categories", "to database"
])


def process_ad_namedtuple(row) -> tuple:
    """Take a given ActivityDataset namedtuple and return two hashable tuples.

    Allows for matching on name/product/location
    """
    match = (row.name, row.product, row.location)
    key = (row.database, row.code)
    return match, key


def constuct_ad_data(row) -> tuple:
    """Take a namedtuple from the method below and convert it into two tuples.

    Used to fill out missing information in the superstructure.
    """
    key = (row.database, row.code)
    if row.type == "process":
        data = (row.name, row.product, row.location, np.NaN, row.database)
    elif "categories" in row.data:
        data = (row.name, np.NaN, np.NaN, row.data["categories"], row.database)
    else:
        data = (row.name, np.NaN, np.NaN, np.NaN, row.database)
    return key, data


def all_flows_found(df: pd.DataFrame, part: str = "from") -> bool:
    """Determines if all activities from the given 'from' or 'to' chunk"""
    select = FROM_BIOS if part == "from" else TO_BIOS
    sub = df.loc[:, select]
    sub = sub[sub.iloc[:, 2] == bw.config.biosphere]  # Use only biosphere exchanges

    names, categories, dbs = sub.iloc[:, 0:3].apply(set, axis=0)
    query = (ActivityDataset
             .select(ActivityDataset.name, ActivityDataset.data, ActivityDataset.database)
             .where((ActivityDataset.name.in_(names)) &
                    (ActivityDataset.database.in_(dbs)))
             .tuples())
    matches = set(
        (x[0], x[1]["categories"], x[2])
        for x in query.iterator() if "categories" in x[1]
    )
    combinations = sub.iloc[:, 0:3].apply(tuple, axis=1)
    return combinations.isin(matches).all()


def all_activities_found(df: pd.DataFrame, part: str = "from") -> bool:
    """Determines if all activities from the given 'from' or 'to' chunk"""
    select = FROM_ACT if part == "from" else TO_ACT
    sub = df.loc[:, select]
    sub = sub[sub.iloc[:, 3] != bw.config.biosphere]  # Exclude biosphere exchanges

    names, products, locations, dbs = sub.iloc[:, 0:4].apply(set, axis=0)
    query = (ActivityDataset
             .select(ActivityDataset.name, ActivityDataset.product, ActivityDataset.location)
             .where((ActivityDataset.name.in_(names)) &
                    (ActivityDataset.product.in_(products)) &
                    (ActivityDataset.location.in_(locations)) &
                    (ActivityDataset.database.in_(dbs)))
             .tuples())
    matches = set(query.iterator())
    combinations = sub.iloc[:, 0:3].apply(tuple, axis=1)
    return combinations.isin(matches).all()


def get_relevant_activities(df: pd.DataFrame) -> dict:
    """Build a dictionary of (name, product, location) -> (database, key) pairs."""
    names, products, locations, dbs = df.iloc[:, 0:4].apply(set, axis=0)
    query = (ActivityDataset
             .select()
             .where((ActivityDataset.name.in_(names)) &
                    (ActivityDataset.product.in_(products)) &
                    (ActivityDataset.location.in_(locations)) &
                    (ActivityDataset.database.in_(dbs)))
             .namedtuples())
    activities = dict(process_ad_namedtuple(x) for x in query.iterator())
    return activities


def convert_fields_to_key(df: pd.DataFrame) -> pd.Series:
    """Converts the process fields to its actual key by matching the database."""
    assert all_activities_found(df), "Some processes could not be found in the database"
    matches = get_relevant_activities(df)
    combinations = df.iloc[:, 0:3].apply(tuple, axis=1)
    keys = pd.Series([matches[x] for x in combinations], dtype="object")
    return keys


def convert_key_to_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Converts the process fields to its actual key by matching the database."""
    keys = set(df.iloc[:, 5])
    dbs, codes = zip(*keys)
    query = (ActivityDataset
             .select()
             .where((ActivityDataset.database.in_(set(dbs))) &
                    (ActivityDataset.code.in_(set(codes))))
             .namedtuples())
    key_data = dict(constuct_ad_data(x) for x in query.iterator())
    subdf = pd.DataFrame([key_data[x] for x in df.iloc[:, 5]], columns=df.columns[0:5])
    return subdf


def fill_out_df_with_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Will attempt to fill out the name, product, category, location and
    database fields using the 'from' and 'to' keys.

    Will raise an Exception if any key is missing in the DataFrame.
    """
    assert df.loc[:, EXCHANGE_KEYS].notna().all().all(), "All keys should be known before running this method."
    from_df = convert_key_to_fields(df.loc[:, FROM_ALL])
    df[from_df.columns] = from_df
    to_df = convert_key_to_fields(df.loc[:, TO_ALL])
    df[to_df.columns] = to_df
    return df


