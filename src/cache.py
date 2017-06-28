import db_util, settings, common_util

class MyCache():
    __user_infos = {}
    __role_infos = {}
    __mysql_host_infos = {}

    def __init__(self):
        pass

    def load_all_cache(self):
        self.load_user_infos()
        self.load_role_infos()
        self.load_mysql_host_infos()

    def load_user_infos(self):
        rows = db_util.DBUtil().fetchall(settings.MySQL_HOST, "select * from mysql_audit.work_user")
        self.__user_infos.clear()
        for row in rows:
            self.__user_infos[row["user_id"]] = common_util.get_object(row)

    def load_role_infos(self):
        rows = db_util.DBUtil().fetchall(settings.MySQL_HOST, "select * from mysql_audit.role_info")
        self.__role_infos.clear()
        for row in rows:
            self.__role_infos[row["role_id"]] = common_util.get_object(row)

    def load_mysql_host_infos(self):
        rows = db_util.DBUtil().fetchall(settings.MySQL_HOST, "select * from mysql_audit.mysql_hosts WHERE is_deleted = 0;")
        self.__mysql_host_infos.clear()
        for row in rows:
            info = common_util.get_object(row)
            info.host = info.ip
            info.key = info.host_id
            self.__mysql_host_infos[row["host_id"]] = info

    def get_user_info(self, user_id=None):
        if(user_id in self.__user_infos.keys()):
            return self.__user_infos[user_id]
        return self.__user_infos.values()

    def get_role_info(self, role_id=None):
        if(role_id in self.__role_infos.keys()):
            return self.__user_infos[role_id]
        return self.__role_infos.values()

    def get_mysql_host_info(self, host_id=None):
        if(host_id in self.__mysql_host_infos.keys()):
            return self.__mysql_host_infos[host_id]
        return self.__mysql_host_infos.values()

