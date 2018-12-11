# coding: utf-8
"""
This module manages Oracle primitives.

    Date:
        23/01/2018

    Author:
        lla11358

    Version:
        0.1

    Notes:

"""

import csv
import logging
import os
import pandas as pd
import shlex
import subprocess
from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.exc import DatabaseError

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


class Oracle:
    """
    Manages connections to Oracle databases.

        Oracle class offers some helper methods that encapsulate primitive
        logic to interactuate with the database: insert/upsert, execute,
        drop, etc.
        Some primitives are not included because they can be handled more
        properly with sqlalchemy.

    """

    def __init__(
            self, user, password, host,
            port, service_name, encoding='utf8'):
        """
        Initialize the database connection and other relevant data.

            Args:
              user(string): database user to connect to the schema.
              password(string): database password of the user.
              host(string): database management system host.
              port(string): tcp port where the database is listening.
              service_name(string): Oracle instance name.
              encoding (string): Charset encoding.
        """
        self.conn_string = "oracle+cx_oracle://{0}:{1}@{2}:{3}/{4}".format(
            user,
            password,
            host,
            port,
            service_name)
        self.engine = create_engine(self.conn_string,
                                    encoding=encoding,
                                    coerce_to_unicode=True,
                                    coerce_to_decimal=False)
        self.schema = user.upper()

    def get_table(self, table_name, schema=None):
        """
        Get a database table into a sqlalchemy Table object.

            Args:
                table_name(string): name of the database table to map.
                schema(string): name of the schema to which the table belongs.
                    Defaults to the selected database in the connection.
            Returns:
                table(Table): sqlalchemy Table object referencing the specified
                    database table.

        """
        meta = MetaData(bind=self.engine,
                        schema=schema if schema else self.schema)
        return Table(table_name, meta, autoload=True,
                     autoload_with=self.engine)

    def execute(self, sql, **kwargs):
        """
        Execute a DDL or DML SQL statement.

            Args:
                sql: SQL statement
            Returns:
                result_set(Dataframe):

        """
        connection = self.engine.connect()
        trans = connection.begin()
        result_set = pd.DataFrame()
        try:
            result = connection.execute(text(sql), **kwargs)
            trans.commit()
            if result.returns_rows:
                result_set = pd.DataFrame(result.fetchall())
                result_set.columns = result.keys()
                LOGGER.info('Number of returned rows: %s',
                            str(len(result_set.index)))
        except DatabaseError as db_error:
            LOGGER.error(db_error)
            raise
        finally:
            connection.close()
        return result_set

    def drop(self, table_name, schema=None):
        """
        Drop a table from the database.

        Args:
          table_name(str): name of the table to drop.

        Returns: nothing.

        """
        if not schema:
            schema = self.schema
        db_table = self.get_table(table_name, schema)
        db_table.drop(self.engine, checkfirst=True)
        LOGGER.info('Table %s.%s successfully dropped.', schema, table_name)

        # Placeholders can only represent VALUES. You cannot use them for
        # sql keywords/identifiers.

    @staticmethod
    def load_data(
        user,
        password,
        host,
        port,
        service_name,
        schema,
        table,
        output_path,
        os_path,
        os_ld_library_path,
        mode="APPEND"):
        """
        Load a dataframe into a table via Oracle SQL Loader.

        Extracts field names and data values from a Pandas DataFrame.
        Requires Oracle Instant Client and Tools installed in the workstation.
        Destination table must exist in the database.
        Usage of SQL Loader:

            sqlldr <user>/<password> control=<control_file> [log=<log_file>]
            [bad=bad_file]

        Args:
            user (str): database user
            password (str): database password
            host: database server host name or IP address
            port (str): Oracle listener port
            service_name (str): Oracle instance service name
            schema (str): database schema
            table (pandas DataFrame): dataframe with the same name and column
                labels as the table in which it's going to be loaded.
                It must be filled with data rows.
            output_path (str): path for output data files
            os_path (str): PATH environment variable
            os_ld_library_path (str): LD_LIBRARY_PATH environment variable
            mode (str): insertion mode: APPEND | REPLACE | TRUNCATE

        """
        columns = ",".join(table.columns.values.tolist())

        # control file
        ctl_file = open('{0}{1}.ctl'.format(output_path, table.name),
                        mode='w',
                        encoding='utf8')
        ctl_header = """LOAD DATA\n""" + \
                     """CHARACTERSET UTF8\n""" + \
                     """INFILE '{0}{1}.dat'\n""".format(
                         output_path, table.name) + \
                     """{0}\n""".format(mode) + \
                     """INTO TABLE {0}.{1}\n""".format(schema, table.name) + \
                     """FIELDS TERMINATED BY ';' """ + \
                     """OPTIONALLY ENCLOSED BY '\"'\n""" + \
                     """TRAILING NULLCOLS\n""" + \
                     """({0})""".format(columns)

        ctl_file.write(ctl_header)
        ctl_file.close()

        # data file
        table.to_csv('{0}{1}.dat'.format(output_path, table.name),
                     sep=';',
                     header=False,
                     index=False,
                     doublequote=True,
                     quoting=csv.QUOTE_NONNUMERIC,
                     encoding='utf-8'
                     )

        # set environment variables
        env = os.environ.copy()
        env['PATH'] = os_path
        env['LD_LIBRARY_PATH'] = os_ld_library_path
        # generate SQL Loader arguments
        os_command = "sqlldr {0}/{1}@{2}:{3}/{4} ".format(
            user, password, host, port, service_name)
        os_command += \
            "control='{0}{1}.ctl' log='{0}{1}.log' bad='{0}{1}.bad'".format(
                output_path, table.name)
        args = shlex.split(os_command)
        # execution of Oracle SQL Loader
        try:
            subprocess.Popen(args, env=env)
        except subprocess.SubprocessError as sproc_error:
            LOGGER.error(sproc_error)
