# -*- coding: utf-8 -*-

import MySQLdb, sys
import settings, common_util

# sql执行备份有两个要求
# 1.必须要有主键
# 2.而且还需要开启binlog
# 3.要使用下面的参数--enable-remote-backup;

reload(sys)
sys.setdefaultencoding("utf8")

sql_audit_flag = "--enable-check;"
sql_execute_flag = "--enable-execute;"
sqL_enable_split_flag = "--enable-split;"
sql_enable_remote_backup = "--enable-remote-backup;"
sql_disable_remote_backup = "--disable-remote-backup;"
sql_enable_ignore_warnings = "--enable-ignore-warnings;"

sql_mode = """/*--host={0};--port={1};--user={2};--password={3};{4}*/
              inception_magic_start;
              {5}
              inception_magic_commit;"""

sql_mode_no_host = "inception_magic_start;{0}inception_magic_commit;"

osc_fields = ["DBNAME", "TABLENAME", "SQLSHA1", "PERCENT", "REMAINTIME", "INFORMATION"]
execute_fields = ['ID', 'stage', 'errlevel', 'stagestatus', 'errormessage', 'SQL', 'Affected_rows', 'sequence', 'backup_dbname', 'execute_time', 'sqlsha1']

'''
id:一个简单的计数。
dest_user:表示当前执行语句访问数据库时所用的用户名。
dest_host:表示当前执行语句要访问的数据库地址。
dest_port:表示当前执行语句要访问的数据库的端口。
from_host:表示当前执行语句是从机器上发起的。
command:表示当前执行的是什么操作，包括CHECK（简单审核），EXECUTE（执行），SPLIT（拆分），PRINT（打印计划树），LOCAL（本地命令）。
state:表示在当前命令下，执行的状态是什么，状态包括INIT（初始阶段），CHECKING（正在审核），EXECUTING（正在执行），DEINIT（退出），BACKUP（正在备份）。
time:表示当前语句执行所用时间。
info:显示当前正在执行的语句。
'''
processlist_fields = ["id", "dest_user", "dest_host", "dest_port", "from_host", "command", "state", "time", "info"]

# sql审核
def sql_audit(sql, host_info):
    sql = sql_mode.format(host_info.host, host_info.port, host_info.user, host_info.password, sql_audit_flag, sql)
    return get_object(execute_sql(sql), fields=execute_fields)


# sql执行
def sql_execute(sql, host_info, is_backup=True, ignore_warnings=False):
    parameters = sql_execute_flag
    parameters += sql_enable_ignore_warnings if (ignore_warnings) else ''
    parameters += sql_enable_remote_backup if (is_backup) else sql_disable_remote_backup
    sql = sql_mode.format(host_info.host, host_info.port, host_info.user, host_info.password, parameters, sql)
    return get_object(execute_sql(sql), fields=execute_fields)


# 停止使用pt-osc的任务sql
def stop_osc_task(sha1_code):
    sql = "inception stop alter '{}';".format(sha1_code)
    return get_object(execute_sql(sql_mode_no_host.format(sql)), fields=osc_fields)


# 获取使用pt-osc的执行精度
# 如果要使用pt-osc，那么在审核的时候就会获得到一个sqlsha1的值
# 那么在真正执行的时候可以获取pt-osc的进度
def get_osc_info(sha1_code):
    sql = "inception get osc_percent '{}';".format(sha1_code)
    return get_object(execute_sql(sql_mode_no_host.format(sql)), fields=osc_fields)


# 获取inception的processlist信息
def get_processlist():
    return get_object(execute_sql("inception get processlist;"), fields=processlist_fields)


# 把返回数据转化为对象
def get_object(rows, fields=None):
    result = []
    if (rows == None or len(rows) <= 0 or fields == None or len(fields) <= 0):
        return result
    for row in rows:
        info = common_util.Entity()
        for i in range(0, len(fields)):
            setattr(info, fields[i].lower(), row[i])
        result.append(info)
    return result


# 连接inception服务器执行sql
def execute_sql(sql):
    connection, cursor = None, None
    try:
        connection = MySQLdb.connect(host=settings.inception_host,
                                     user=settings.inception_user,
                                     passwd=settings.inception_password,
                                     port=settings.inception_port,
                                     use_unicode=True, charset="utf8", connect_timeout=2)
        cursor = connection.cursor()
        cursor.execute(sql)
        return cursor.fetchall()
    finally:
        if (cursor != None):
            cursor.close()
        if (connection != None):
            connection.close()
    return []
