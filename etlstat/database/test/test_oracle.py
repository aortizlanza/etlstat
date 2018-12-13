# -*- coding: utf-8 -*-

"""Unit tests for oracle database module."""

import os
import unittest
import pandas
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy import (select, func, Column, Integer, String, Boolean, Float,
                        DateTime)
from sqlalchemy.ext.declarative import declarative_base
from etlstat.database.oracle import Oracle

os.environ['NLS_LANG'] = '.AL32UTF8'


class TestOracle(unittest.TestCase):
    """Testing methods for Oracle class."""

    user = 'test'
    password = 'password'
    host = 'localhost'
    port = '1521'
    service_name = 'xe'
    conn_params = [user, password, host, port, service_name]
    output_path = os.getcwd() + '/etlstat/database/test/'
    os_path = '/usr/local/bin:/usr/bin:/bin:' \
        '/opt/oracle/instantclient_12_2'
    os_ld_library_path = '/opt/oracle/instantclient_12_2'

    @classmethod
    def setUpClass(cls):
        """Set up test variables."""
        user = 'system'
        password = 'oracle'
        host = 'localhost'
        port = '1521'
        service_name = 'xe'
        conn_params = [user, password, host, port, service_name]
        ora_conn = Oracle(*conn_params)
        sql = "DROP USER TEST CASCADE"
        ora_conn.execute(sql)
        sql = "CREATE USER test IDENTIFIED BY password " \
              "DEFAULT TABLESPACE USERS TEMPORARY TABLESPACE TEMP"
        ora_conn.execute(sql)
        sql = "ALTER USER test QUOTA UNLIMITED ON USERS"
        ora_conn.execute(sql)
        sql = "GRANT CONNECT, RESOURCE TO test"
        ora_conn.execute(sql)

    def test_init(self):
        """Check connection with Oracle database."""
        self.assertEqual(
            str(Oracle(*self.conn_params).engine),
            "Engine(oracle+cx_oracle://test:***@localhost:1521/xe)")

    def test_execute(self):
        """Check if different queries are correctly executed."""
        ora_conn = Oracle(*self.conn_params)
        sql = "CREATE TABLE table1 (id integer, column1 varchar2(100), " \
              "column2 number)"
        ora_conn.execute(sql)
        table1 = ora_conn.get_table('table1')
        self.assertEqual(table1.c.column1.name, 'column1')
        sql = "INSERT INTO table1 (id, column1, column2) " \
              "VALUES (1, 'Varchar text (100 char)', " \
              "123456789.012787648484859)"
        ora_conn.execute(sql)  # EXECUTE example
        # The select.columns parameter is not available in the method form of
        # select(), e.g. FromClause.select().
        # See https://docs.sqlalchemy.org/en/latest/core/selectable.html#
        # sqlalchemy.sql.expression.FromClause.select
        results = ora_conn.engine.execute(
            select([table1.c.column1]).select_from(table1)).fetchall()
        expected = 'Varchar text (100 char)'
        current = results[0][0]
        # this returns a tuple inside a list and I dont know why
        self.assertEqual(expected, current)
        query = 'select * from table1 order by id'
        result = ora_conn.execute(query)
        expected = 1
        current = len(result.index)
        self.assertEqual(expected, current)
        ora_conn.drop('table1')

    def test_select(self):
        """Check select statement using sqlalchemy."""
        ora_conn = Oracle(*self.conn_params)
        table_name = "audit_actions"
        schema = "sys"
        audit_actions = ora_conn.get_table(table_name, schema=schema)
        # SELECT * FROM sys.audit_actions
        # WHERE name like 'CREATE%' AND action > 100
        results = ora_conn.engine.execute(
            select('*').where(
                audit_actions.c.name.like('CREATE%')).where(
                    audit_actions.c.action > 100).select_from(
                        audit_actions)).fetchall()
        table_df = pandas.DataFrame(results)
        self.assertGreaterEqual(len(table_df), 17)

    def test_get_table(self):
        """Check get table from the database using SqlAlchemy."""
        ora_conn = Oracle(*self.conn_params)
        hlp = ora_conn.get_table('help', schema='system')  # GET TABLE example
        row_count = ora_conn.engine.scalar(
            select([func.count('*')]).select_from(hlp)
        )
        # The select.columns parameter is not available in the method form of
        # select(), e.g. FromClause.select().
        # See https://docs.sqlalchemy.org/en/latest/core/selectable.html#
        # sqlalchemy.sql.expression.FromClause.select
        ora_conn.engine.execute(
            select([hlp.c.info]).select_from(hlp))
        self.assertEqual(row_count, 919)

    def test_create(self):
        """Check create table using sqlalchemy."""
        Base = declarative_base()
        ora_conn = Oracle(*self.conn_params)

        # table creation can be done via execute() + raw SQL or using this:
        class Table2(Base):
            """Auxiliary sqlalchemy table model for the tests."""

            __tablename__ = 'table2'

            column_int = Column(Integer)
            column_string = Column(String(20))
            column_float = Column(Float)
            column_datetime = Column(DateTime)
            column_boolean = Column(Boolean)
            id = Column(Integer, primary_key=True)

        Table2.__table__.create(bind=ora_conn.engine)
        table2 = ora_conn.get_table('table2')
        self.assertEqual(table2.c.column_datetime.name, 'column_datetime')
        self.assertEqual(len(table2.c), 6)
        ora_conn.drop('table2')

    def test_drop(self):
        """Check drop for an existing table."""
        ora_conn = Oracle(*self.conn_params)
        sql = "CREATE TABLE table1 (id INTEGER, column1 VARCHAR(100), " \
            "column2 NUMBER)"
        ora_conn.execute(sql)
        ora_conn.get_table('table1')
        ora_conn.drop('table1')  # DROP example
        with self.assertRaises(InvalidRequestError):
            ora_conn.get_table('table1')

    def test_delete(self):
        """Check delete rows from table."""
        ora_conn = Oracle(*self.conn_params)
        sql = "CREATE TABLE test_delete (column_int INTEGER," \
            "column_string VARCHAR(100), column_float NUMBER)"
        ora_conn.execute(sql)
        sql1 = "INSERT INTO test_delete (column_int, column_string, " \
            "column_float) VALUES(2, 'string2', 456.956)"
        sql2 = "INSERT INTO test_delete (column_int, column_string, " \
            "column_float) VALUES(1, 'string1', 38.905)"
        ora_conn.execute(sql1)
        ora_conn.execute(sql2)
        table = ora_conn.get_table('test_delete')
        expected = 2
        current = ora_conn.engine.scalar(
            select([func.count('*')]).select_from(table)
        )
        self.assertEqual(current, expected)
        # delete from operation
        table.delete().where(table.c.column_int == 2).execute()
        expected = 1
        current = ora_conn.engine.scalar(
            select([func.count('*')]).select_from(table)
        )
        self.assertEqual(current, expected)
        ora_conn.drop('test_delete')

    def test_insert(self):
        """Check if a bulk insert with sql loader is correctly executed."""
        table_name = 'px_01001'
        ora_conn = Oracle(*self.conn_params)
        sql = "CREATE TABLE {0} (id INTEGER, tipo_indicador " \
            "VARCHAR(100), nivel_educativo VARCHAR(100), valor NUMBER)". \
            format(table_name)
        ora_conn.execute(sql)
        px_01001 = ora_conn.get_table(table_name)
        self.assertTrue(px_01001.exists)
        source_file = self.output_path + 'px_01001.csv'
        data_file = self.output_path + 'px_01001.dat'
        control_file = self.output_path + 'px_01001.ctl'
        log_file = self.output_path + 'px_01001.log'
        bad_file = self.output_path + 'px_01001.bad'
        data_columns = ['id', 'tipo_indicador', 'nivel_educativo', 'valor']
        table_def = pandas.DataFrame(columns=data_columns)
        table_def['id'] = table_def['id'].astype(int)
        table_def['tipo_indicador'] = table_def['tipo_indicador'].astype(str)
        table_def['nivel_educativo'] = table_def['nivel_educativo'].astype(str)
        table_def['valor'] = table_def['valor'].astype(float)
        table_def.name = table_name
        data = pandas.read_csv(source_file, header=0, sep=';', encoding='utf8')
        data.name = table_name
        ora_conn.insert(
            *self.conn_params,
            schema=self.conn_params[0],
            table=data,
            output_path=self.output_path,
            os_path=self.os_path,
            os_ld_library_path=self.os_ld_library_path
        )
        self.assertTrue(os.path.isfile(data_file))
        os.remove(data_file)
        self.assertTrue(os.path.isfile(control_file))
        os.remove(control_file)
        self.assertTrue(os.path.isfile(log_file))
        os.remove(log_file)
        self.assertFalse(os.path.isfile(bad_file))


if __name__ == '__main__':
    unittest.main()
