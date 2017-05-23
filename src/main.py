# -*- coding: utf8 -*-

import json, datetime, SpliceURL, time, os, jinja2
from flask import request, g, render_template, redirect, make_response, url_for
from flask_multistatic import MultiStaticFlask
from config import GLOBAL, SSO, PLUGINS, REDIS
from utils.tool import logger, sso_logger, access_logger, plugin_logger, isLogged_in, md5, Initialization
from urllib import urlencode
from libs.api import ApiManager
from views.api import api_blueprint
from views.front import front_blueprint
from views.admin import admin_blueprint
from views.upload import upload_blueprint
from plugins.AccessCount import AccessCountPluginManager

__author__  = 'Mr.tao'
__email__   = 'staugur@saintic.com'
__doc__     = 'A flask+mysql+bootstrap blog based on personal interests and hobbies.'
__date__    = '2017-03-26'
__org__     = 'SaintIC'
__version__ = '0.0.1'

ac = AccessCountPluginManager()
#初始化定义application
app  = MultiStaticFlask(__name__)
#自定义模板文件夹
loader = jinja2.ChoiceLoader([
    app.jinja_loader,
    jinja2.FileSystemLoader(['plugins/p1/templates/','plugins/p2/templates/']),
])
app.jinja_loader = loader
#自定义静态文件夹
app.static_folder = [
    os.path.join(app.root_path, 'plugins', "p1", "static"),
    os.path.join(app.root_path, 'static', 'default')
]
#初始化接口管理器
api  = ApiManager()
#实例化初始化类并执行
init = Initialization()
plugin_logger.info("Initialization Plugins End")
#注册蓝图路由,可以修改前缀
app.register_blueprint(front_blueprint)
app.register_blueprint(api_blueprint, url_prefix="/api")
app.register_blueprint(admin_blueprint, url_prefix="/admin")
app.register_blueprint(upload_blueprint, url_prefix="/upload")

@app.before_request
def before_request():
    g.startTime = time.time()
    g.sessionId = request.cookies.get("sessionId", "")
    g.username  = request.cookies.get("username", "")
    g.expires   = request.cookies.get("time", "")
    g.signin    = isLogged_in('.'.join([ g.username, g.expires, g.sessionId ]))
    g.sysInfo   = {"Version": __version__, "Author": __author__, "Email": __email__, "Doc": __doc__}
    g.api       = api
    g.plugins   = PLUGINS
    g.hitCache  = False

@app.after_request
def after_request(response):
    data = {
        "status_code": response.status_code,
        "method": request.method,
        "ip": request.headers.get('X-Real-Ip', request.remote_addr),
        "url": request.url,
        "referer": request.headers.get('Referer'),
        "agent": request.headers.get("User-Agent"),
        "TimeInterval": "%0.2fs" %float(time.time() - g.startTime)
    }
    access_logger.info(json.dumps(data))
    app.logger.debug(dir(ac))
    ac.Record_ip_pv(data["ip"])
    #g.api.ClickMysqlWrite(data)
    if request.endpoint != 'static':
        return response
    response.cache_control.max_age = 86400 #1d
    return response

@app.errorhandler(404)
def not_found(error=None):
    return render_template('public/404.html'),404

@app.errorhandler(500)
def server_error(error=None):
    return render_template('public/500.html'),500

@app.route('/login/')
def login():
    if g.signin:
        return redirect(url_for("front.index"))
    else:
        query = {"sso": True,
           "sso_r": SpliceURL.Modify(request.url_root, "/sso/").geturl,
           "sso_p": SSO["SSO.PROJECT"],
           "sso_t": md5("%s:%s" %(SSO["SSO.PROJECT"], SpliceURL.Modify(request.url_root, "/sso/").geturl))
        }
        SSOLoginURL = SpliceURL.Modify(url=SSO["SSO.URL"], path="/login/", query=query).geturl
        sso_logger.info("User request login to SSO: %s" %SSOLoginURL)
        return redirect(SSOLoginURL)

@app.route('/logout/')
def logout():
    SSOLogoutURL = SSO.get("SSO.URL") + "/sso/?nextUrl=" + request.url_root.strip("/")
    resp = make_response(redirect(SSOLogoutURL))
    resp.set_cookie(key='logged_in', value='', expires=0)
    resp.set_cookie(key='username',  value='', expires=0)
    resp.set_cookie(key='sessionId',  value='', expires=0)
    resp.set_cookie(key='time',  value='', expires=0)
    resp.set_cookie(key='Azone',  value='', expires=0)
    return resp

@app.route('/sso/')
def sso():
    ticket = request.args.get("ticket")
    sso_logger.info("ticket: %s" %ticket)
    username, expires, sessionId = ticket.split('.')
    if expires == 'None':
        UnixExpires = None
    else:
        UnixExpires = datetime.datetime.strptime(expires,"%Y-%m-%d")
    resp = make_response(redirect(url_for("front.index")))
    resp.set_cookie(key='logged_in', value="yes", expires=UnixExpires)
    resp.set_cookie(key='username',  value=username, expires=UnixExpires)
    resp.set_cookie(key='sessionId', value=sessionId, expires=UnixExpires)
    resp.set_cookie(key='time', value=expires, expires=UnixExpires)
    resp.set_cookie(key='Azone', value="sso", expires=UnixExpires)
    return resp

@app.route('/SignUp')
def signup():
    regUrl = SSO.get("SSO.URL").strip("/") + "/SignUp"
    return redirect(regUrl)

if __name__ == '__main__':
    Port  = GLOBAL.get('Port')
    app.run(host="0.0.0.0", port=int(Port), debug=True)
