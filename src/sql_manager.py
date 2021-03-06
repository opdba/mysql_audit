# -*- coding: utf-8 -*-

import json, time, traceback
from flask import render_template, request
import inception_util, cache, db_util, settings, common_util


# 根据sql和主机id审核sql
def audit_sql(obj):
    obj.sql = get_use_db_sql(obj.sql, obj.db_name)
    return render_template("audit_view.html", audit_infos=inception_util.sql_audit(obj.sql, cache.MyCache().get_mysql_host_info(obj.host_id)))


# 根据sql_id获取sql进行审核
def audit_sql_by_sql_id(sql_id):
    sql_info = get_sql_info_by_id(sql_id)
    sql_info.sql_value = get_use_db_sql(sql_info.sql_value, sql_info.execute_db_name)
    return render_template("audit_view.html", audit_infos=inception_util.sql_audit(sql_info.sql_value, cache.MyCache().get_mysql_host_info(sql_info.mysql_host_id)))


# 获取审核的数据库主机信息
def get_audit_mysql_host():
    return cache.MyCache().get_mysql_host_info()


# 获取执行的数据库主机信息
def get_execute_mysql_host():
    return cache.MyCache().get_mysql_host_info()


# 添加工单时应该自动审核一下比较好
# 状态 0：未审核 1：已审核 2：审核不通过 3：执行错误 4：执行成功 5：执行中 6：工单已撤销
def add_sql_work(obj):
    try:
        audit_result = inception_util.sql_audit(get_use_db_sql(obj.sql_value, obj.db_name), cache.MyCache().get_mysql_host_info(obj.host_id))
        if (get_sql_execute_status(audit_result) == False):
            return "提交的SQL有错误，请审核之后在提交！"

        user_info = cache.MyCache().get_user_info(obj.current_user_id)
        sql = """INSERT INTO `mysql_audit`.`sql_work`
                 (`create_user_id`, `audit_user_id`, `execute_user_id`,
                  `audit_date_time`, `execute_date_time`,
                  `mysql_host_id`, `jira_url`, `is_backup`, `backup_table`, `sql_value`,
                  `return_value`, `status`, `title`, `audit_result_value`, `execute_db_name`, `create_user_group_id`)
                 VALUES
                 ({0}, {1}, {1}, NOW(), NULL, {2}, '{3}', {4}, '', '{5}', '', {6}, '{7}', '{8}', '{9}', {10});""" \
            .format(obj.current_user_id,
                    obj.dba_user_id,
                    obj.host_id,
                    db_util.DBUtil().escape(obj.jira_url),
                    obj.is_backup,
                    db_util.DBUtil().escape(obj.sql_value),
                    settings.SQL_AUDIT_OK,
                    db_util.DBUtil().escape(obj.title),
                    db_util.DBUtil().escape(json.dumps(audit_result, default=lambda o: o.__dict__)),
                    obj.db_name,
                    user_info.group_id)
        db_util.DBUtil().execute(settings.MySQL_HOST, sql)
        return "提交SQL工单成功"
    except Exception, e:
        traceback.print_exc()
        return e.message


# 增加编辑未执行的工单功能
# 修改标题，jira地址，是否备份，执行sql的DBA
# sql和上线的库为什么不可以修改，主要是如果你写错了，那么审核的时候肯定就不通过的
def update_sql_work(obj):
    sql = """update `mysql_audit`.`sql_work` set `title` = '{0}', `jira_url` = '{1}', `execute_user_id` = {2}, is_backup = {3} where id = {4};""" \
        .format(db_util.DBUtil().escape(obj.title),
                db_util.DBUtil().escape(obj.jira_url), obj.dba_user_id, obj.is_backup, obj.sql_id)
    db_util.DBUtil().execute(settings.MySQL_HOST, sql)
    return "update ok."


# 根据id删除工单
def delete_sql_work(sql_id):
    db_util.DBUtil().execute(settings.MySQL_HOST, "update `mysql_audit`.`sql_work` set is_deleted = 1 where id = {0}".format(sql_id))
    return "delete ok."


# 根据查询条件获取工单列表-有分页功能
def get_sql_list(obj):
    sql_where = ""
    if (int(obj.status) >= 0):
        sql_where += " and status = {0}".format(obj.status)
    if (int(obj.user_id) > 0):
        sql_where += " and create_user_id = {0}".format(obj.user_id)
    if (len(obj.start_datetime) > 0):
        sql_where += " and created_time >= '{0}'".format(obj.start_datetime)
    if (len(obj.stop_datetime) > 0):
        sql_where += " and created_time <= '{0}'".format(obj.stop_datetime)

    # 这边要根据用户权限进行查询
    # 管理员可以看所有的用户
    # 开发只能看到自己提交的工单
    # 组长只能看到组员提交的所有工单
    user_info = cache.MyCache().get_user_info(obj.current_user_id)
    if (user_info.group_id == settings.ADMIN_GROUP_ID):
        pass
    elif (user_info.group_id == settings.DBA_GROUP_ID):
        if (user_info.role_id == settings.ROLE_DEV):
            sql_where += " and (create_user_id = {0} or execute_user_id = {0})".format(obj.current_user_id)
        else:
            pass
    elif (user_info.role_id == settings.ROLE_DEV):
        sql_where += " and create_user_id = {0}".format(obj.current_user_id)
    elif (user_info.role_id == settings.ROLE_LEADER):
        sql_where += " and create_user_group_id = {0}".format(user_info.group_id)

    """sql = select t1.id, t1.title, t1.create_user_id, t1.audit_user_id, t1.execute_user_id, t1.audit_date_time,
                    t1.execute_date_time, t1.mysql_host_id, t1.jira_url, t1.is_backup,
                    t1.backup_table, left(sql_value, 10) as sql_value, t1.return_value, t1.status, t1.is_deleted, t1.created_time,
                    t2.host_name, t3.chinese_name, ifnull(t4.chinese_name, '') as execute_user_name, t1.execute_db_name
             from mysql_audit.sql_work t1
             left join `mysql_audit`.mysql_hosts t2 on t1.mysql_host_id = t2.host_id
             left join mysql_audit.work_user t3 on t1.create_user_id = t3.user_id
             left join mysql_audit.work_user t4 on t1.execute_user_id = t4.user_id
             where t1.is_deleted = 0 {0} order by t1.id desc limit {1}, {2};"""

    # 下周来完成权限控制
    # 除了DBA组和Admin可以执行SQL以外，任何组都没有执行权限
    # 不过可以考虑一下组长可以执行
    # DBA只能看到指定给自己执行的工单以及自己创建的工单
    # 只有admin才能看到所以的工单

    sql = """select t1.*, t2.host_name, t3.chinese_name, ifnull(t4.chinese_name, '') as execute_user_name
             from
             (
                 select id, title, create_user_id, audit_user_id, execute_user_id, audit_date_time,
                        execute_date_time, mysql_host_id, jira_url, is_backup, execute_db_name,
                        backup_table, left(sql_value, 10) as sql_value, status, is_deleted, created_time, execute_finish_date_time
                 from mysql_audit.sql_work
                 where is_deleted = 0 {0} order by id desc limit {1}, {2}
             ) t1
             left join mysql_audit.mysql_hosts t2 on t1.mysql_host_id = t2.host_id
             left join mysql_audit.work_user t3 on t1.create_user_id = t3.user_id
             left join mysql_audit.work_user t4 on t1.execute_user_id = t4.user_id ORDER BY t1.id DESC """
    sql = sql.format(sql_where, (obj.page_number - 1) * settings.SQL_LIST_PAGE_SIZE, settings.SQL_LIST_PAGE_SIZE)
    result_list = db_util.DBUtil().get_list_infos(settings.MySQL_HOST, sql)
    for info in result_list:
        get_sql_work_status_name(info)
    return result_list


# 组员账号获取工单列表的方法
def get_sql_list_for_dev(type_id):
    # 所有工单
    # 审核中的工单
    # 已执行的工单
    if (type_id == 1):
        sql = ""
    pass


# 根据工单id获取全部信息
def get_sql_info_by_id(id):
    sql = """select t1.sql_value, t1.title, t1.jira_url, t1.execute_user_id, t1.is_backup,
                    t1.ignore_warnings, rollback_sql, ifnull(t4.chinese_name, '') as execute_user_name,
                    t2.host_name, t3.chinese_name, t1.mysql_host_id, t1.id, t1.status, t3.email,
                    t1.return_value, t1.execute_db_name, t1.audit_result_value, t1.execute_user_id, t1.created_time, ifnull(t1.execute_date_time, '') as execute_date_time
             from `mysql_audit`.`sql_work` t1
             left join `mysql_audit`.mysql_hosts t2 on t1.mysql_host_id = t2.host_id
             left join mysql_audit.work_user t3 on t1.create_user_id = t3.user_id
             left join mysql_audit.work_user t4 on t1.execute_user_id = t4.user_id
             where t1.id = {0};""".format(id)
    return get_sql_work_status_name(common_util.get_object(db_util.DBUtil().fetchone(settings.MySQL_HOST, sql)))


# 执行sql并更新工单状态
# 状态 0：未审核 1：已审核 2：审核不通过 3：执行错误 4：执行成功
def sql_execute(obj):
    try:
        sql_info = get_sql_info_by_id(obj.sql_id)
        if (sql_info.status == settings.SQL_EXECUTE_SUCCESS):
            # 如果已经执行成功，直接返回执行结果
            return json.loads(sql_info.return_value)
        else:
            # 更新工单状态为执行中
            sql = "update mysql_audit.sql_work set `status` = {0}, `execute_start_date_time` = NOW(), `execute_date_time` = NOW() where id = {1};"\
                  .format(settings.SQL_EXECUTE_ING, sql_info.id)
            db_util.DBUtil().execute(settings.MySQL_HOST, sql)

            if (len(sql_info.execute_db_name.strip()) > 0):
                sql_info.sql_value = "use {0};{1}".format(sql_info.execute_db_name, sql_info.sql_value)
            result_obj = inception_util.sql_execute(sql_info.sql_value,
                                                    cache.MyCache().get_mysql_host_info(sql_info.mysql_host_id),
                                                    is_backup=sql_info.is_backup,
                                                    ignore_warnings=True if (obj.ignore_warnings.upper() == "TRUE") else False)
            sql = """update mysql_audit.sql_work
                     set
                     return_value = '{0}',
                     `status` = {1},
                     `ignore_warnings` = {2},
                     `execute_finish_date_time` = NOW(),
                     `real_execute_user_id` = {3} where id = {4};""" \
                  .format(db_util.DBUtil().escape(json.dumps(result_obj, default=lambda o: o.__dict__)),
                          settings.SQL_EXECUTE_SUCCESS if (get_sql_execute_status(result_obj)) else settings.SQL_EXECUTE_FAIL,
                          obj.ignore_warnings,
                          obj.current_user_id,
                          sql_info.id,)
            db_util.DBUtil().execute(settings.MySQL_HOST, sql)
            send_mail_for_execute_success(sql_info.id)
            return result_obj
    except:
        # 出现异常要更新状态，直接把状态变为fail
        sql = "update mysql_audit.sql_work set `status` = {0} where id = {1};".format(settings.SQL_EXECUTE_FAIL, sql_info.id)
        db_util.DBUtil().execute(settings.MySQL_HOST, sql)
        traceback.print_exc()
        return "sql execute fail"


# 停止正在执行的sql
def stop_sql_execute(obj):
    pass


# 如果审核结果有warning，那么要提示用户选择忽视警告执行SQL
def check_sql_audit_result_has_warnings(sql_id):
    result = common_util.Entity()
    sql_info = get_sql_info_by_id(sql_id)
    for info in json.loads(sql_info.audit_result_value):
        obj = common_util.get_object(info)
        if (obj.errlevel == settings.INCETION_SQL_WARNING):
            result.has_warnings = True
            break
        else:
            result.has_warnings = False
    return json.dumps(result, default=lambda o: o.__dict__)


# 获取执行成功的SQL执行结果
def get_sql_result(sql_id):
    sql_info = get_sql_info_by_id(sql_id)
    # 根据状态返回相应的结果，审核状态返回审核结果，执行状态返回执行结果
    if (sql_info.status == settings.SQL_AUDIT_OK or sql_info.status == settings.SQL_AUDIT_FAIL):
        return render_template("audit_view.html", audit_infos=json.loads(sql_info.audit_result_value))
    elif (sql_info.status == settings.SQL_EXECUTE_ING or sql_info.status == settings.SQL_EXECUTE_FAIL or sql_info.status == settings.SQL_EXECUTE_SUCCESS):
        return render_template("sql_execute_view.html", audit_infos=json.loads(sql_info.return_value))


# 获取sql执行状态的中文
# 状态 0：未审核 1：已审核 2：审核不通过 3：执行错误 4：执行成功 5：执行中 6：工单已撤销
def get_sql_work_status_name(sql_info):
    sql_info.status_name = settings.SQL_WORK_STATUS_DICT[sql_info.status]
    return sql_info


# 获取sql审核或执行的状态
# True：执行或审核没有错误
# False：执行或审核出现严重错误
def get_sql_execute_status(result):
    for info in result:
        if (info.errlevel == settings.INCETION_SQL_ERROR):
            return False
    return True


# 获取审核或执行结果是否有警告状态
def get_sql_result_has_warning_status(result):
    for info in result:
        if (info.errlevel == settings.INCETION_SQL_WARNING):
            return False
    return True


# 获取对应数据库的所以库名称
def get_database_names(host_id):
    html_str = """<select id="db_name" name="db_name" class="selectpicker show-tick form-control bs-select-hidden">
                      <option value="0" disabled selected style="color: black">请选择要执行的库:</option>
                      {0}
                  </select>"""
    options_str = ""
    result = db_util.DBUtil().get_list_infos(cache.MyCache().get_mysql_host_info(host_id=host_id), "show databases;")
    for num in range(0, len(result)):
        db_name = result[num].Database;
        # 过滤掉系统库
        if (db_name != "information_schema" and db_name != "mysql" and db_name != "sys" and db_name != "performance_schema"):
            options_str += "<option value=\"{0}\">{1}</option>".format(db_name, db_name)
    return html_str.format(options_str)


# 获取使用use db的完整sql
def get_use_db_sql(sql_value, db_name):
    if (db_name != None):
        return "use {0};{1}".format(db_name, sql_value)
    return sql_value


# 查看回滚SQL语句
def get_rollback_sql(sql_id):
    aa = time.time()
    result = common_util.Entity()
    sql_info = get_sql_info_by_id(sql_id)
    result.rollback_sql = []
    result.rollback_sql_value = ""
    result.is_backup = sql_info.is_backup
    result.host_id = sql_info.mysql_host_id
    if (sql_info.is_backup):
        if (sql_info.rollback_sql != None):
            result.rollback_sql_value = sql_info.rollback_sql
        else:
            for info in json.loads(sql_info.return_value):
                info = common_util.get_object(info)
                if (info.backup_dbname == None):
                    continue
                sql = "select schema_name from information_schema.SCHEMATA where schema_name = '{0}';".format(info.backup_dbname)
                db_name = db_util.DBUtil().fetchone(settings.MySQL_HOST, sql)
                if (db_name == None):
                    continue
                sql = "select tablename from {0}.$_$Inception_backup_information$_$ where opid_time = {1}".format(info.backup_dbname, info.sequence)
                table_name_dict = db_util.DBUtil().fetchone(settings.MySQL_HOST, sql)
                if (table_name_dict == None):
                    continue
                sql = "select rollback_statement from {0}.{1} where opid_time = {2}".format(info.backup_dbname, table_name_dict["tablename"], info.sequence)
                for list_dict in db_util.DBUtil().fetchall(settings.MySQL_HOST, sql):
                    result.rollback_sql.append(list_dict.values()[0])
    bb = time.time()
    print(">>>>>>>>>>>>>>get rollback sql time:{0}<<<<<<<<<<<<<<<<<<<".format(bb - aa))
    if (len(result.rollback_sql) > 0):
        result.rollback_sql_value = "\n".join(result.rollback_sql)
        result.rollback_sql = []
        db_util.DBUtil().execute(settings.MySQL_HOST,
                                 "update mysql_audit.sql_work set `rollback_sql` = '{0}' where id = {1};".format(db_util.DBUtil().escape(result.rollback_sql_value), sql_id))
    return result


# 执行回滚语句
def execute_rollback_sql(sql_id):
    sql_info = get_sql_info_by_id(sql_id)
    rollback_host = cache.MyCache().get_mysql_host_info(int(sql_info.mysql_host_id))
    rollback_sql = "start transaction; " + get_rollback_sql(sql_id).rollback_sql_value + " commit;"
    if (db_util.DBUtil().execute(rollback_host, rollback_sql)):
        db_util.DBUtil().execute(settings.MySQL_HOST, "update mysql_audit.sql_work set `status` = {0} where id = {1};".format(settings.SQL_WORK_ROLLBACK, sql_id))
        return "回滚成功"
    return "回滚失败"


# 审核成功发送邮件
def send_mail_for_audit_success():
    if (settings.EMAIL_SEND_ENABLE):
        pass


# 执行成功发送邮件
def send_mail_for_execute_success(sql_id):
    if (settings.EMAIL_SEND_ENABLE):
        sql_info = get_sql_info_by_id(sql_id)
        sql_info.status_str = settings.SQL_WORK_STATUS_DICT[sql_info.status]
        sql_info.host_url = request.host_url
        if (len(sql_info.email) > 0):
            subject = "SQL工单-[{0}]-执行完成".format(sql_info.title)
            sql_info.work_url = "{0}sql/work/{1}".format(request.host_url, sql_info.id)
            content = render_template("mail_template.html", sql_info=sql_info)
            common_util.send_html(subject, sql_info.email, content)

