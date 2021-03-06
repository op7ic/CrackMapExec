from logger import *
from impacket.smbconnection import SessionError
import socket
import settings
import os
import csv
import StringIO

class MSSQLSessionError(Exception):
    pass

def smart_login(host, domain, connection, cme_logger):
    '''
        This function should probably be called ugly_login
    ''' 
    fails = 0

    if settings.args.combo_file:
        with open(settings.args.combo_file, 'r') as combo_file:
            for line in combo_file:
                try:

                    if settings.args.fail_limit:
                        if settings.args.fail_limit == fails:
                            cme_logger.info('Reached login fail limit')
                            raise socket.error
                    
                    if settings.args.gfail_limit:
                        if settings.gfails >= settings.args.gfail_limit:
                            cme_logger.info('Reached global login fail limit')
                            raise socket.error

                    line = line.strip()

                    lmhash = ''
                    nthash = ''

                    if '\\' in line:
                        domain, user_pass = line.split('\\')
                    else:
                        user_pass = line

                    '''
                        Here we try to manage two cases: if an entry has a hash as the password,
                        or, in the unlikely event, the plain-text password contains a ':' (pfft who am I kidding)
                    '''
                    if len(user_pass.split(':')) == 3:
                        hash_or_pass = ':'.join(user_pass.split(':')[1:3]).strip()

                        #Not the best way to determine of it's an NTLM hash :/
                        if len(hash_or_pass) == 65 and len(hash_or_pass.split(':')[0]) == 32 and len(hash_or_pass.split(':')[1]) == 32:
                            lmhash, nthash = hash_or_pass.split(':')
                            passwd = hash_or_pass
                            user = user_pass.split(':')[0]

                    elif len(user_pass.split(':')) == 2:
                        user, passwd = user_pass.split(':')

                    try:
                        if settings.args.kerb:
                            if settings.args.mssql is not None:
                                res = connection.kerberosLogin(None, user, passwd, domain, ':'.join([lmhash, nthash]), settings.args.aesKey)
                                if res is not True:
                                    connection.printReplies()
                                    raise MSSQLSessionError
                            else:
                                connection.kerberosLogin(user, passwd, domain, lmhash, nthash, settings.args.aesKey)

                        else:
                            if settings.args.mssql is not None:
                                res = connection.login(None, user, passwd, domain, ':'.join([lmhash, nthash]), True)
                                if res is not True:
                                    connection.printReplies()
                                    raise MSSQLSessionError
                            else:
                                connection.login(user, passwd, domain, lmhash, nthash)

                        cme_logger.success(u"Login successful {}\\{}:{}".format(domain, user, passwd))

                        settings.args.user = user
                        settings.args.passwd = passwd
                        settings.args.hash = ':'.join([lmhash, nthash])
                        
                        return connection
                    
                    except SessionError as e:
                        cme_logger.error(u"{}\\{}:{} {}".format(domain, user, passwd, e))
                        if 'STATUS_LOGON_FAILURE' in e:
                            fails += 1
                            settings.gfails += 1
                        continue

                    except MSSQLSessionError:
                        fails += 1
                        settings.gfails += 1
                        continue

                except Exception as e:
                    cme_logger.error("Error parsing line '{}' in combo file: {}".format(line, e))
                    continue
    else:
        usernames = []
        passwords = []
        hashes    = []

        if settings.args.user is not None:
            if os.path.exists(settings.args.user):
                usernames = open(settings.args.user, 'r')
            else:
                usernames = settings.args.user.split(',')

        if settings.args.passwd is not None:
            if os.path.exists(settings.args.passwd):
                passwords = open(settings.args.passwd, 'r')
            else:
                '''
                    You might be wondering: wtf is this? why not use split()?
                    This is in case a password contains a comma (lol!), we can use '\\' to make sure it's parsed correctly
                    IMHO this is a much better (much lazier) way than writing a custom split() function
                '''
                try:
                    passwords = csv.reader(StringIO.StringIO(settings.args.passwd), delimiter=',', escapechar='\\').next()
                except StopIteration:
                    #in case we supplied only '' as the password (null session)
                    passwords = ['']

        if settings.args.hash is not None:
            if os.path.exists(settings.args.hash):
                hashes = open(settings.args.hash, 'r')
            else:
                hashes = settings.args.hash.split(',')

        for user in usernames:
            user = user.strip()

            try:
                hashes.seek(0)
            except AttributeError:
                pass

            try:
                passwords.seek(0)
            except AttributeError:
                pass

            if hashes:
                for ntlm_hash in hashes:

                    if settings.args.fail_limit:
                        if settings.args.fail_limit == fails:
                            cme_logger.info('Reached login fail limit')
                            raise socket.error
                    
                    if settings.args.gfail_limit:
                        if settings.gfails >= settings.args.gfail_limit:
                            cme_logger.info('Reached global login fail limit')
                            raise socket.error

                    ntlm_hash = ntlm_hash.strip().lower()
                    lmhash, nthash = ntlm_hash.split(':')
                    if user == '': user = "''"

                    try:
                        if settings.args.kerb:
                            if settings.args.mssql is not None:
                                res = connection.kerberosLogin(None, user, '', domain, ':'.join([lmhash, nthash]), settings.args.aesKey)
                                if res is not True:
                                    connection.printReplies()
                                    raise MSSQLSessionError  
                            else:
                                connection.kerberosLogin(user, '', domain, lmhash, nthash, settings.args.aesKey)
                        else:
                            if settings.args.mssql is not None:
                                res = connection.login(None, user, '', domain, ':'.join([lmhash, nthash]), True)
                                if res is not True:
                                    connection.printReplies()
                                    raise MSSQLSessionError
                            else:
                                connection.login(user, '', domain, lmhash, nthash)
                        
                        cme_logger.success(u"Login successful {}\\{}:{}".format(domain, user, ntlm_hash))
                        settings.args.user = user
                        settings.args.hash = ntlm_hash
                        
                        return connection

                    except SessionError as e:
                        cme_logger.error(u"{}\\{}:{} {}".format(domain, user, ntlm_hash, e))
                        if 'STATUS_LOGON_FAILURE' in str(e):
                            fails += 1
                            settings.gfails += 1
                        continue

                    except MSSQLSessionError:
                        fails += 1
                        settings.gfails += 1
                        continue

            if passwords:
                for passwd in passwords:

                    if settings.args.fail_limit:
                        if settings.args.fail_limit == fails:
                            cme_logger.info('Reached login fail limit')
                            raise socket.error

                    if settings.args.gfail_limit:
                        if settings.gfails >= settings.args.gfail_limit:
                            cme_logger.info('Reached global login fail limit')
                            raise socket.error

                    passwd = passwd.strip()
                    if user == '': user = "''"
                    if passwd == '': passwd = "''"
                    try:
                        if settings.args.kerb:
                            if settings.args.mssql is not None:
                                connection.kerberosLogin(None, user, passwd, domain, None, settings.args.aesKey)
                                if res is not True:
                                    connection.printReplies()
                                    raise MSSQLSessionError
                            else:
                                connection.kerberosLogin(user, passwd, domain, '', '', settings.args.aesKey)
                        else:
                            if settings.args.mssql is not None:
                                res = connection.login(None, user, passwd, domain, None, True)
                                if res is not True:
                                    connection.printReplies()
                                    raise MSSQLSessionError
                            else:
                                connection.login(user, passwd, domain)

                        cme_logger.success(u"Login successful {}\\{}:{}".format(domain, user, passwd))
                        settings.args.user = user
                        settings.args.passwd = passwd
                        
                        return connection

                    except SessionError as e:
                        cme_logger.error(u"{}\\{}:{} {}".format(domain, user, passwd, e))
                        if 'STATUS_LOGON_FAILURE' in str(e):
                            fails += 1
                            settings.gfails += 1
                        continue

                    except MSSQLSessionError:
                        fails += 1
                        settings.gfails += 1
                        continue

    raise socket.error #So we fail without a peep