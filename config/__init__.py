# Lets Django use PyMySQL as its MySQL driver (easy to install everywhere)
import pymysql
pymysql.version_info = (2, 2, 1, "final", 0)
pymysql.install_as_MySQLdb()
