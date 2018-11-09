import sqlite3

try:
    from tabulate import tabulate
except ModuleNotFoundError:
    print('run pip install tabulate to print tables')

"""
The attached geopackage contains Public Data from the US Census and Virginia Board of Elections and can be accessed
in its raw  format here:
- https://www.census.gov/geo/maps-data/data/tiger.html
- https://apps.elections.virginia.gov/SBE_CSV/ELECTIONS/ELECTIONRESULTS/

It contains 5 tables:
    - VirginiaXXXX, Feature tables with median income per VA county for year (title) and polygon
        outlining the county
    - tl_2016_51_cousub is a polygon table of individual districts with in VA. These can be
        grouped by the column 'countyfp'
    - county_pop_2010 contains the VA county Populations for 2010
    - general_election2006 are the VA county election results for the 2006 general election
"""

# Connect to the GPKG

gpkgFile = 'Census_Income_VA.gpkg'
connection = sqlite3.connect(gpkgFile)
cursor = connection.cursor()

# Clear Previously Created Views

clear="""DELETE FROM gpkg_geometry_columns WHERE table_name = '{0}';
DELETE FROM gpkg_contents where table_name = '{0}';
DROP VIEW {0};"""

views=['county_election_results','average_income','population','party_breakdown']
for i in views:
    try:
        cursor.executescript(clear.format(i))
    except sqlite3.OperationalError:
        continue




#print tables in gpkg_contents, then print slqite_master information

query1 = """SELECT g.table_name, g.data_type, s.name, s.type FROM gpkg_contents g
                JOIN sqlite_master s ON s.name = g.table_name
"""
cursor.execute(query1)
headers = ['gpkg_table_name','data_type','slqite_master_table_name','sql_type']
print(tabulate([list(data) for data in cursor.fetchall()],headers=headers))








# Create View
#     - Average median income (medianinco) across all VirginiaXXXX Tables
#     - JOIN district geometries to counties through countyfp
#



query2="""CREATE VIEW average_income AS
                SELECT m.name as county, t.name as district, m.avg_income, t.geom as geometry FROM
                    (SELECT m.name, m.countyfp, avg(m.medianinco) as avg_income FROM
                        (SELECT countyfp, name, medianinco from virginia2003
        		               UNION
        	             SELECT countyfp, name, medianinco from virginia2006
        		               UNION
        	             SELECT countyfp, name, medianinco from virginia2009
        		               UNION
        	             SELECT countyfp, name, medianinco from virginia2012
        		               UNION
        	             SELECT countyfp, name, medianinco from virginia2015
        	                ) m
        	                   GROUP BY m.name, m.countyfp ) m
        	    JOIN tl_2016_51_cousub t ON t.countyfp = m.countyfp;

           INSERT INTO gpkg_contents (table_name, identifier, data_type, srs_id) VALUES ( 'average_income', 'average_income', 'features', 4326);
           INSERT INTO gpkg_geometry_columns (table_name, column_name, geometry_type_name, srs_id, z, m) VALUES('average_income','geometry','MUTIPOLYGON',4326,0,0);"""



cursor.execute("SELECT * FROM sqlite_master where name = 'average_income'")
if cursor.fetchall() == []:
    cursor.executescript(query2)
else:
    cursor.executescript(clear.format('average_income'))
    cursor.executescript(query2)


# create a view of county populations joined to the district geometries

query3 = """ CREATE VIEW population AS
                SELECT p.couname as county, t.name as district, cast(p.population as int) as population, t.geom as geometry FROM tl_2016_51_cousub t
                	JOIN county_pop_2010 p ON p.countyfp = t.countyfp;
                    INSERT INTO gpkg_contents (table_name, identifier, data_type, srs_id) VALUES ( 'population', 'population', 'features', 4326);
                    INSERT INTO gpkg_geometry_columns (table_name, column_name, geometry_type_name, srs_id, z, m) VALUES('population','geometry','MUTIPOLYGON',4326,0,0);"""


cursor.execute("SELECT * FROM sqlite_master where name = 'population'")
if cursor.fetchall() == []:
    cursor.executescript(query3)
else:
    print(True)
    cursor.executescript(clear.format('population'))
    cursor.executescript(query3)


# Create a view of election results joined to the district geometry


query4 = """CREATE VIEW county_election_results AS
            SELECT g.localityname, g.party, g.total_votes, p.population, t.geom as geometry FROM
                (select localityname, coalesce(party,'Write In') as party, sum(total_votes) as total_votes from general_election2006 GROUP BY localityname, party) g
                    JOIN
                (select countyfp, couname || ' COUNTY' as county, population from county_pop_2010) p ON p.county = g. localityname COLLATE NOCASE
            JOIN tl_2016_51_cousub t ON t.countyfp=p.countyfp;
            INSERT INTO gpkg_contents (table_name, identifier, data_type, srs_id) VALUES ( 'county_election_results', 'county_election_results', 'features', 4326);
            INSERT INTO gpkg_geometry_columns (table_name, column_name, geometry_type_name, srs_id, z, m) VALUES('county_election_results','geometry','MUTIPOLYGON',4326,0,0);"""




cursor.execute("SELECT * FROM sqlite_master where name = 'county_election_results'")
if cursor.fetchall() == []:
    cursor.executescript(query4)
else:
    print(True)
    cursor.executescript(clear.format('county_election_results'))
    cursor.executescript(query4)



# Create a view that creates a column for the individual parties that participated in the election JOINed to the county polygons in Virginia2003

query5 = """CREATE VIEW party_breakdown AS
        SELECT c.county, d.total_votes as Democratic,
				 i.total_votes as Independent,
				 ig.total_votes as IndependentGreen,
				 l.total_votes as Libertarian,
				 r.total_votes as Republican,
				 w.total_votes as WriteIn,
				 v.geom as geometry
				FROM
                	(select localityname as county from general_election2006 group by localityname) c
                		LEFT JOIN
                	(select localityname as county, sum(total_votes) as total_votes from county_election_results where party='Democratic' group by localityname, party) d on d.county = c.county
                		LEFT JOIN
                	(select localityname as county, sum(total_votes) as total_votes from county_election_results where party='Independent' group by localityname, party) i on i.county = c.county
                		LEFT JOIN
                	(select localityname as county, sum(total_votes) as total_votes from county_election_results where party='Independent Green' group by localityname, party) ig on ig.county = c.county
                		LEFT JOIN
                	(select localityname as county, sum(total_votes) as total_votes from county_election_results where party='Libertarian' group by localityname, party) l on l.county = c.county
                		LEFT JOIN
                	(select localityname as county, sum(total_votes) as total_votes from county_election_results where party='Republican' group by localityname, party) r on r.county = c.county
                		LEFT JOIN
                	(select localityname as county, sum(total_votes) as total_votes from county_election_results where party IS NULL  group by localityname, party) w on w.county = c.county
                		JOIN Virginia2003 v ON v.name || ' COUNTY' = c.county collate NOCASE;
                INSERT INTO gpkg_contents (table_name, identifier, data_type, srs_id) VALUES ( 'party_breakdown', 'party_breakdown', 'features', 4326);
                INSERT INTO gpkg_geometry_columns (table_name, column_name, geometry_type_name, srs_id, z, m) VALUES('party_breakdown','geometry','MUTIPOLYGON',4326,0,0);"""





cursor.execute("SELECT * FROM sqlite_master where name = 'party_breakdown'")
if cursor.fetchall() == []:
    cursor.executescript(query5)
else:
    print(True)
    cursor.executescript(clear.format('county_election_results'))
    cursor.executescript(query5)










#print tables in gpkg_contents, then print slqite_master information again to show the newly created views.

cursor.execute(query1)
headers = ['gpkg_table_name','data_type','slqite_master_table_name','sql_type']
print(tabulate([list(data) for data in cursor.fetchall()],headers=headers))
connection.close()
