#####
#
# Module name:  dremail.com
# Purpose:      Manage email connections for dupReport
# 
# Notes:
#
#####

# Import system modules
import imaplib
import poplib
import email
import re
import datetime
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Import dupReport modules
import globs
import drdatetime


#Define message segments (line parts) for Duplicati result email messages
# lineParts[] are the individual line items in the Duplicati status email report.
# 1 - internal variable name
# 2 - Duplicati name from email and regex to find it
# 3 - regex flags. 0=none.
# 4 - field Type (0=int or 1=str)
lineParts = [
    ('deletedFiles','DeletedFiles: \d+', 0, 0),
    ('deletedFolders', 'DeletedFolders: \d+', 0, 0),
    ('modifiedFiles', 'ModifiedFiles: \d+', 0, 0),
    ('examinedFiles', 'ExaminedFiles: \d+', 0, 0),
    ('openedFiles', 'OpenedFiles: \d+', 0, 0),
    ('addedFiles', 'AddedFiles: \d+', 0, 0),
    ('sizeOfModifiedFiles', 'SizeOfModifiedFiles: .*', 0, 0),
    ('sizeOfAddedFiles', 'SizeOfAddedFiles: .*', 0, 0),
    ('sizeOfExaminedFiles', 'SizeOfExaminedFiles: .*', 0, 0),
    ('sizeOfOpenedFiles', 'SizeOfOpenedFiles: .*', 0, 0),
    ('notProcessedFiles', 'NotProcessedFiles: \d+', 0, 0),
    ('addedFolders', 'AddedFolders: \d+', 0, 0),
    ('tooLargeFiles', 'TooLargeFiles: \d+', 0, 0),
    ('filesWithError', 'FilesWithError: \d+', 0, 0),
    ('modifiedFolders', 'ModifiedFolders: \d+', 0, 0),
    ('modifiedSymlinks', 'ModifiedSymlinks: \d+', 0, 0),
    ('addedSymlinks', 'AddedSymlinks: \d+', 0, 0),
    ('deletedSymlinks', 'DeletedSymlinks: \d+', 0, 0),
    ('partialBackup', 'PartialBackup: \w+', 0, 1),
    ('dryRun', 'Dryrun: \w+', 0, 1),
    ('mainOperation', 'MainOperation: \w+', 0, 1),
    ('parsedResult', 'ParsedResult: \w+', 0, 1),
    ('verboseOutput', 'VerboseOutput: \w+', 0, 1),
    ('verboseErrors', 'VerboseErrors: \w+', 0, 1),
    ('endTimeStr', 'EndTime: .*', 0, 1),
    ('beginTimeStr', 'BeginTime: .*', 0, 1),
    ('duration', 'Duration: .*', 0, 1),
    ('messages', 'Messages: \[.*^\]', re.MULTILINE|re.DOTALL, 1),
    ('warnings', 'Warnings: \[.*^\]', re.MULTILINE|re.DOTALL, 1),
    ('errors', 'Errors: \[.*^\]', re.MULTILINE|re.DOTALL, 1),
    ('details','Details: .*', re.MULTILINE|re.DOTALL, 1),
    ('failed', 'Failed: .*', re.MULTILINE|re.DOTALL, 1),
    ]


class EmailServer:
    def __init__(self, prot, add, prt, acct, pwd, crypt, kalive, fold = None):
        self.protocol = prot
        self.address = add
        self.port = prt
        self.accountname = acct
        self.passwd = pwd
        self.encryption = crypt
        self.keepalive = kalive
        self.folder = fold
        self.server = None
        self.newEmails = 0      # List[] of new emails on server. Activated by connect()
        self.numEmails = 0      # Number of emails in list
        self.nextEmail = 0      # index into list of next email to be retrieved

    def dump(self):
        return 'protocol=[{}] address=[{}] port=[{}] account=[{}] passwd=[{}] encryption=[{}] keepalive=[{}] folder=[{}]'.format(self.protocol, self.address, self.port, self.accountname, self.passwd, self.encryption, self.keepalive, self.folder)

    def connect(self):
        globs.log.write(1, 'EmailServer.Connect({})'.format(self.dump()))
        globs.log.write(3, 'server={} keepalive={}'.format(self.server, self.keepalive))

        # See if a server connection is already established
        # This is the most common case, so check this first
        if self.server != None:
            if self.keepalive is False: # Do we care about keepalives?
                return None

            globs.log.write(3,'Cheeking server connection')
            if self.protocol == 'imap':
                try:
                    status = self.server.noop()[0]
                except:
                    status = 'NO'

                if status != 'OK':
                    globs.log.write(1,'Server {} timed out. Reconnecting.'.format(self.address))
                    self.server = None
                    self.connect()
            elif self.protocol == 'pop3':
                try:
                    status = self.server.noop()
                except:
                    status = '+NO'

                if status != '+OK':
                    globs.log.write(1,'Server {} timed out. Reconnecting.'.format(self.address))
                    self.server = None
                    self.connect()
            elif self.protocol == 'smtp':
                try:
                    status = self.server.noop()[0]
                except:  # smtplib.SMTPServerDisconnected
                    status = -1

                if status != 250: # Disconnected. Need to reconnect to server
                    globs.log.write(1,'Server {} timed out. Reconnecting.'.format(self.address))
                    self.server = None
                    self.connect()
        else:     # Need to establish server connection
            if self.protocol == 'imap':
                globs.log.write(1,'Initial connect using  IMAP')
                try:
                    if self.encryption is not None:
                        self.server = imaplib.IMAP4_SSL(self.address,self.port)
                    else:
                        self.server = imaplib.IMAP4(self.address,self.port)
                    retVal, data = self.server.login(self.accountname, self.passwd)
                    globs.log.write(3,'IMAP Logged in. retVal={} data={}'.format(retVal, data))
                    retVal, data = self.server.select(self.folder)
                    globs.log.write(3,'IMAP Setting folder. retVal={} data={}'.format(retVal, data))
                    return retVal
                except imaplib.IMAP4.error:
                    return None
                except imaplib.socket.gaierror:
                    return None
            elif self.protocol == 'pop3':
                globs.log.write(1,'Initial connect using POP3')
                try:
                    if self.encryption is not None:
                        self.server = poplib.POP3_SSL(self.address,self.port)
                    else:
                        self.server = poplib.POP3(self.address,self.port)
                    retVal = self.server.user(self.accountname)
                    globs.log.write(3,'Logged in. retVal={}'.format(retVal))
                    retVal = self.server.pass_(self.passwd)
                    globs.log.write(3,'Entered password. retVal={}'.format(retVal))
                    return retVal.decode()
                except Exception:
                    return None
            elif self.protocol == 'smtp':
                globs.log.write(1,'Initial connect using  SMTP')
                try:
                    self.server = smtplib.SMTP('{}:{}'.format(self.address,self.port))
                    if self.encryption is not None:   # Do we need to use SSL/TLS?
                        self.server.starttls()
                    retVal, retMsg = self.server.login(self.accountname, self.passwd)
                    globs.log.write(3,'Logged in. retVal={} retMsg={}'.format(retVal, retMsg))
                    return retMsg.decode()
                except (smtplib.SMTPAuthenticationError, smtplib.SMTPConnectError, smtplib.SMTPSenderRefused):
                    return None
            else:   # Bad protocol specification
                globs.log.err('Invalid protocol specification: {}. Aborting program.'.format(self.protocol))
                globs.closeEverythingAndExit(1)
                return None
        return None


    # Close email server connection
    def close(self):
        if self.server == None:
            return None

        if self.protocol == 'pop3':
            self.server.quit()
        elif self.protocol == 'imap':
            self.server.close()
        elif self.protocol == 'smtp':
            self.server.quit()
        return None

    # Check if there are new messages waiting on the server
    # Return number of messages if there
    # Return None if empty
    def checkForMessages(self):
        self.connect()
        if self.protocol == 'pop3':
            globs.log.write(1,'checkForMessages(POP3)')
            self.numEmails = len(self.server.list()[1])  # Get list of new emails
            globs.log.write(3,'Number of new emails: {}'.format(self.numEmails))
            if self.numEmails == 0:     # No new emails
                self.newEmails = None 
                self.nextEmail = 0      
                return None
            self.newEmails = list(range(self.numEmails))
            self.nextEmail = -1     # processNextMessage() pre-increments message index. Initializing to -1 ensures the pre-increment start at 0
            return self.numEmails
        elif self.protocol == 'imap':
            globs.log.write(1,'checkForMessages(IMAP)')
            retVal, data = self.server.search(None, "ALL")
            globs.log.write(3,'Searching folder. retVal={} data={}'.format(retVal, data))
            if retVal != 'OK':          # No new emails
                self.newEmails = None
                self.numEmails = 0
                self.nextEmail = 0
                return None
            self.newEmails = list(data[0].split())   # Get list of new emails
            self.numEmails = len(self.newEmails)          
            self.nextEmail = -1     # processNextMessage() pre-increments message index. Initializing to -1 ensures the pre-increment start at 0
            return self.numEmails
        else:  # Invalid protocol
            return None


    # Extract a (parentheses) field or raw data from the result
    # Some fields (sizes, date, time) can be presented in text or numeric values (Starting with Canary builds in Jan 2018)
    # Examples: EndTime: 1/24/2018 10:01:45 PM (1516852905)
    #           SizeOfAddedFiles: 10.12 KB (10364)
    #           SizeOfExaminedFiles: 44.42 GB (47695243956)
    # This function will return the value in parentheses (if it exists) or the raw info (if it does not)
    # Inputs: val = value to parse, dt = date format string, tf = time format string
    def parenOrRaw(self, val, df = None, tf = None, tz = None):
        globs.log.write(1,'dremail.parenOrRaw({}, {}, {}, {})'.format(val, df, tf, tz))
        
        retval = val    # Set default return as input value

        # Search for '(XXX)' in value
        pat = re.compile('\(.*\)')
        match = re.search(pat, val)
        if match:  # value found in parentheses
            retval = val[match.regs[0][0]+1:match.regs[0][1]-1]
        else:  # No parens found
            if df != None:  # Looking for date/time
                retval = drdatetime.toTimestamp(val, dfmt=df, tfmt=tf, utcOffset=tz)

        globs.log.write(1, 'retval=[{}]'.format(retval))
        return retval

    # Extract specific fields from an email header
    # Different email servers create email headers diffrently
    # Also, fields like Subject can be split across multiple lines
    # Our mission is to sort it all out
    # Return date, subject, message-id
    def extractHeaders(self, hdrs):
        globs.log.write(3,'dremail.extractHeaders({})'.format(hdrs))
        posLocs1 = []
        posLocs2 = {}

        hdr2 = hdrs.replace('\n', ' ')      # Create a copy of the headers data without newlines
        for match in re.finditer('[A-Za-z-]+:', hdr2):                  # "<string>:" indicates the start of a header field. Find all instances of that in the data
            tit = hdrs[match.regs[0][0]:match.regs[0][1]-1]             # Get the name of the field
            posLocs1.append((tit, match.regs[0][0], match.regs[0][1]))  # Append the field name and the start/end locations of the field title to the list
        posLen = len(posLocs1)
        for i in range(posLen-1):                                       # Loop through most of header fields in data
            # Different servers use different capilatlzations for field names
            # Use lower() in the following because it makes it easier to match names
            posLocs2[posLocs1[i][0].lower()] = hdrs[posLocs1[i][2]+1:posLocs1[i+1][1]-1].replace('\n','').replace('\r','')      # Get string starting from ':'+1 through to beginning of next field, then remove \r & \n
        posLocs2[posLocs1[posLen-1][0].lower()] = hdrs[posLocs1[posLen-1][2]+1:len(hdrs)].replace('\n','').replace('\r','')     # Do same for last header in the data

        globs.log.write(2,'Header fields extracted: date=[{}] subject=[{}]  message-id=[{}]'.format(posLocs2['date'], posLocs2['subject'], posLocs2['message-id']))
        return posLocs2['date'], posLocs2['subject'], posLocs2['message-id']
    
    # Retrieve and process next message from server
    # Returns <Message-ID> or '<INVALID>' if there are more messages in queue, even if this message was unusable
    # Returns None if no more messages
    def processNextMessage(self):
        globs.log.write(1, 'dremail.processNextMessage()')
        self.connect()

        # Increment message counter to the next message. 
        # Skip for message #0 because we haven't read any messages yet
        self.nextEmail += 1

        msgParts = {}       # msgParts contains extracts of message elements
        statusParts = {}    # statusParts contains the individual lines from the Duplicati status emails
        dateParts = {}      # dateParts contains the date & time strings for the SQL Query

        # Check no-more-mail conditions. Either no new emails to get or gone past the last email on list
        if (self.newEmails == None) or (self.nextEmail == self.numEmails):  
            return None

        if self.protocol == 'pop3':
            # Get message header
            server_msg, body, octets = self.server.top((self.newEmails[self.nextEmail])+1,0)
            globs.log.write(3, 'server_msg=[{}]  body=[{}]  octets=[{}]'.format(server_msg,body,octets))
            if server_msg[:3].decode() != '+OK':
                globs.log.write(1, 'ERROR getting message: {}'.format(self.nextEmail))
                return '<INVALID>'

            # Get date, subject, and message ID from headers
            msgParts['date'], msgParts['subject'], msgParts['messageId'] = self.extractHeaders(body.decode('utf-8'))

        elif self.protocol == 'imap':
            # Get message header
            retVal, data = self.server.fetch(self.newEmails[self.nextEmail],'(BODY.PEEK[HEADER.FIELDS (DATE SUBJECT MESSAGE-ID)])')
            if retVal != 'OK':
                globs.log.write(1, 'ERROR getting message: {}'.format(self.nextEmail))
                return '<INVALID>'
            globs.log.write(3,'Server.fetch(): retVal=[{}] data=[{}]'.format(retVal,data))

            msgParts['date'], msgParts['subject'], msgParts['messageId'] = self.extractHeaders(data[0][1].decode('utf-8'))
            
        else:   # Invalid protocol spec
            globs.log.err('Invalid protocol specification: {}.'.format(self.protocol))
            return None
            
        # Log message basics
        globs.log.write(1,'\n*****\nNext Message: Date=[{}] Subject=[{}] Message-Id=[{}]'.format(msgParts['date'], msgParts['subject'], msgParts['messageId']))
        
        # Check if any of the vital parts are missing
        if msgParts['messageId'] is None or msgParts['messageId'] == '':
            globs.log.write(1,'No message-Id. Abandoning processNextMessage()')
            return '<INVALID>'
        if msgParts['date'] is None or msgParts['date'] == '':
            globs.log.write(1,'No Date. Abandoning processNextMessage()')
            return msgParts['messageId']
        if msgParts['subject'] is None or msgParts['subject'] == '':
            globs.log.write(1,'No Subject. Abandoning processNextMessage()')
            return msgParts['messageId']

        # See if it's a message of interest
        # Match subject field against 'subjectregex' parameter from RC file (Default: 'Duplicati Backup report for...')
        if re.search(globs.opts['subjectregex'], msgParts['subject']) == None:
            globs.log.write(1, 'Message [{}] is not a Message of Interest. Can\'t match subjectregex from .rc file. Skipping message.'.format(msgParts['messageId']))
            return msgParts['messageId']    # Not a message of Interest

        # Get source & desination computers from email subject
        srcRegex = '{}{}'.format(globs.opts['srcregex'], re.escape(globs.opts['srcdestdelimiter']))
        destRegex = '{}{}'.format(re.escape(globs.opts['srcdestdelimiter']), globs.opts['destregex'])
        globs.log.write(3,'srcregex=[{}]  destRegex=[{}]'.format(srcRegex, destRegex))
        partsSrc = re.search(srcRegex, msgParts['subject'])
        partsDest = re.search(destRegex, msgParts['subject'])
        if (partsSrc is None) or (partsDest is None):    # Correct subject but delimeter not found. Something is wrong.
            globs.log.write(2,'SrcDestDelimeter [{}] not found in subject line. Skipping message.'.format(globs.opts['srcdestdelimiter']))
            return msgParts['messageId']

        # See if the record is already in the database, meaning we've seen it before
        if globs.db.searchForMessage(msgParts['messageId']):    # Is message is already in database?
            # Mark the email as being seen in the database
            globs.db.execSqlStmt('UPDATE emails SET dbSeen = 1 WHERE messageId = \"{}\"'.format(msgParts['messageId']))
            globs.db.dbCommit()
            return msgParts['messageId']
        # Message not yet in database. Proceed.
        globs.log.write(1, 'Message ID [{}] does not yet exist in DB.'.format(msgParts['messageId']))

        dTup = email.utils.parsedate_tz(msgParts['date'])
        if dTup:
            # See if there's timezone info in the email header data. May be 'None' if no TZ info in the date line
            # TZ info is represented by seconds offset from UTC
            # We don't need to adjust the email date for TimeZone info now, since date line in email already accounts for TZ.
            # All other calls to toTimestamp() should include timezone info
            msgParts['timezone'] = dTup[9]

            # Set date into a parseable string
            # It doesn't matter what date/time format we pass in (as long as it's valid)
            # When it comes back out later, it'll be parsed into the user-defined format from the .rc file
            # For now, we'll use YYYY/MM/DD HH:MM:SS
            xDate = '{:04d}/{:02d}/{:02d} {:02d}:{:02d}:{:02d}'.format(dTup[0], dTup[1], dTup[2], dTup[3], dTup[4], dTup[5])  
            dtTimStmp = drdatetime.toTimestamp(xDate, dfmt='YYYY/MM/DD', tfmt='HH:MM:SS')  # Convert the string into a timestamp
            msgParts['emailTimestamp'] = dtTimStmp
            globs.log.write(3, 'emailDate=[{}]-[{}]'.format(dtTimStmp, drdatetime.fromTimestamp(dtTimStmp)))

        msgParts['sourceComp'] = re.search(srcRegex, msgParts['subject']).group().split(globs.opts['srcdestdelimiter'])[0]
        msgParts['destComp'] = re.search(destRegex, msgParts['subject']).group().split(globs.opts['srcdestdelimiter'])[1]
        globs.log.write(3, 'sourceComp=[{}] destComp=[{}] emailTimestamp=[{}] subject=[{}]'.format(msgParts['sourceComp'], \
            msgParts['destComp'], msgParts['emailTimestamp'], msgParts['subject']))

        # Search for source/destination pair in database. Add if not already there
        retVal = globs.db.searchSrcDestPair(msgParts['sourceComp'], msgParts['destComp'])

        # Extract the body (payload) from the email
        if self.protocol == 'pop3':
            # Retrieve the whole messsage. This is redundant with previous .top() call and results in extra data downloads
            # In cases where there is a mix of Duplicati and non-Duplicati emails to read, this actually saves time in the large scale.
            # In cases where all the emails on the server are Duplicati emails, this does, in fact, slow things down a bit
            # POP3 is a stupid protocol. Use IMAP if at all possible.
            server_msg, body, octets = self.server.retr((self.newEmails[self.nextEmail])+1)
            msgTmp=''
            for j in body:
                msgTmp += '{}\n'.format(j.decode("utf-8"))
            msgBody = email.message_from_string(msgTmp)._payload  # Get message body
        elif self.protocol == 'imap':
            # Retrieve just the body text of the message.
            retVal, data = self.server.fetch(self.newEmails[self.nextEmail],'(BODY.PEEK[TEXT])')
        
            # Fix issue #71
            # From https://stackoverflow.com/questions/2230037/how-to-fetch-an-email-body-using-imaplib-in-python
            # "...usually the data format is [(bytes, bytes), bytes] but when the message is marked as unseen manually, 
            # the format is [bytes, (bytes, bytes), bytes] – Niklas R Sep 8 '15 at 23:29
            # Need to check if len(data)==2 (normally unread) or ==3 (manually set unread)
            globs.log.write(3,'dataLen={}'.format(len(data)))
            if len(data) == 2:
                msgBody = data[0][1].decode('utf-8')  # Get message body
            else:
                msgBody = data[1][1].decode('utf-8')  # Get message body
        
        globs.log.write(3, 'Message Body=[{}]'.format(msgBody))

        # Go through each element in lineParts{}, get the value from the body, and assign it to the corresponding element in statusParts{}
        for section,regex,flag,typ in lineParts:
            statusParts[section] = self.searchMessagePart(msgBody, regex, flag, typ) # Get the field parts

        # Adjust fields if not a clean run
        globs.log.write(3, "statusParts['failed']=[{}]".format(statusParts['failed']))
        if statusParts['failed'] == '':  # Looks like a good run
            # These fields can be included in parentheses in later versions of Duplicati
            # For example:
            #   SizeOfModifiedFiles: 23 KB (23556)
            #   SizeOfAddedFiles: 10.12 KB (10364)
            #   SizeOfExaminedFiles: 44.42 GB (47695243956)
            #   SizeOfOpenedFiles: 33.16 KB (33954)
            # Extract the parenthesized value (if present) or the raw value (if not)
            dt, tm = globs.optionManager.getRcSectionDateTimeFmt(msgParts['sourceComp'], msgParts['destComp'])
            dateParts['endTimestamp'] = self.parenOrRaw(statusParts['endTimeStr'], df = dt, tf = tm, tz = msgParts['timezone'])
            dateParts['beginTimestamp'] = self.parenOrRaw(statusParts['beginTimeStr'], df = dt, tf = tm, tz = msgParts['timezone'])
            globs.log.write(3, 'Email indicates a successful backup. Date/time is: end=[{}]  begin=[{}]'.format(dateParts['endTimestamp'], dateParts['beginTimestamp'])), 

            statusParts['sizeOfModifiedFiles'] = self.parenOrRaw(statusParts['sizeOfModifiedFiles'])
            statusParts['sizeOfAddedFiles'] = self.parenOrRaw(statusParts['sizeOfAddedFiles'])
            statusParts['sizeOfExaminedFiles'] = self.parenOrRaw(statusParts['sizeOfExaminedFiles'])
            statusParts['sizeOfOpenedFiles'] = self.parenOrRaw(statusParts['sizeOfOpenedFiles'])

        else:  # Something went wrong. Let's gather the details.
            statusParts['errors'] = statusParts['failed']
            statusParts['parsedResult'] = 'Failure'
            statusParts['warnings'] = statusParts['details']
            globs.log.write(2, 'Errors=[{}]'.format(statusParts['errors']))
            globs.log.write(2, 'Warnings=[{}]'.format(statusParts['warnings']))

            # Since the backup job report never ran, we'll use the email date/time as the report date/time
            dateParts['endTimestamp'] = msgParts['emailTimestamp']
            dateParts['beginTimestamp'] = msgParts['emailTimestamp']
            globs.log.write(3, 'Email indicates a failed backup. Replacing date/time with: end=[{}]  begin=[{}]'.format(dateParts['endTimestamp'], dateParts['beginTimestamp'])), 

        # Replace commas (,) with newlines (\n) in message fields. Sqlite really doesn't like commas in SQL statements!
        for part in ['messages', 'warnings', 'errors']:
            if statusParts[part] != '':
                    statusParts[part] = statusParts[part].replace(',','\n')

        # If we're just collecting and get a warning/error, we may need to send an email to the admin
        if (globs.opts['collect'] is True) and (globs.opts['warnoncollect'] is True) and ((statusParts['warnings'] != '') or (statusParts['errors'] != '')):
            errMsg = 'Duplicati error(s) on backup job\n'
            errMsg += 'Message ID {} on {}\n'.format(msgParts['messageId'], msgParts['date'])
            errMsg += 'Subject: {}\n\n'.format(msgParts['subject'])
            if statusParts['warnings'] != '':
                errMsg += 'Warnings:' + statusParts['warnings'] + '\n\n'
            if statusParts['errors'] != '':
                errMsg += 'Errors:' + statusParts['errors'] + '\n\n'

            globs.outServer.sendErrorEmail(errMsg)

        globs.log.write(3, 'Resulting timestamps: endTimeStamp=[{}] beginTimeStamp=[{}]'.format(drdatetime.fromTimestamp(dateParts['endTimestamp']), drdatetime.fromTimestamp(dateParts['beginTimestamp'])))
            
        sqlStmt = self.buildEmailSql(msgParts, statusParts, dateParts)
        globs.db.execSqlStmt(sqlStmt)
        globs.db.dbCommit()

        return msgParts['messageId']


    # Search for field in message
    # msgField - text to search against
    # regex - regex to search for
    # multiLine - 0=single line, 1=multi-line
    # type - 0=int or 1=string
    def searchMessagePart(self, msgField, regex, multiLine, typ):
        globs.log.write(1, 'EmailServer.searchMesagePart(msgField, {}, {}, {}'.format(regex, multiLine, typ))

        match = re.compile(regex, multiLine).search(msgField)  # Search msgField for regex match
        if match:  # Found a match - regex is in msgField
            if multiLine == 0:   # Single line result
                grpSplit =  match.group().split()  # Split matching text into "words"
                grpLen = len(grpSplit)
                retData = ''
                for num in range(1, len(grpSplit)):   # Loop through number of 'words' expeced
                    retData = retData + grpSplit[num]  # Add current 'word' to result
                    if (num < (grpLen - 1)):
                        retData = retData + ' '    # Add spaces between words, but not at the end
            else:    # Multi-line result
                retData = match.group()    # Group the multi-line data
                retData = re.sub(re.compile(r'\s+'), ' ', retData)  # Convert multiple white space to a single space
                retData = re.sub(re.compile(r'\"'), '\'', retData)  # Convert double quotes to single quotes
        else:  # Pattern not found
            if typ == 0:  # Integer field
                retData = '0'
            else:         # String field
                retData = ''

        return retData

    # Build SQL statement to put into the emails table
    def buildEmailSql(self, mParts, sParts, dParts):  

        globs.log.write(1, 'build_email_sql_statement(()')
        globs.log.write(2, 'messageId={}  sourceComp={}  destComp={}'.format(mParts['messageId'],mParts['sourceComp'],mParts['destComp']))

        sqlStmt = "INSERT INTO emails(messageId, sourceComp, destComp, emailTimestamp, \
            deletedFiles, deletedFolders, modifiedFiles, examinedFiles, \
            openedFiles, addedFiles, sizeOfModifiedFiles, sizeOfAddedFiles, sizeOfExaminedFiles, \
            sizeOfOpenedFiles, notProcessedFiles, addedFolders, tooLargeFiles, filesWithError, \
            modifiedFolders, modifiedSymlinks, addedSymlinks, deletedSymlinks, partialBackup, \
            dryRun, mainOperation, parsedResult, verboseOutput, verboseErrors, endTimestamp, \
            beginTimestamp, duration, messages, warnings, errors, dbSeen) \
            VALUES \
            ('{}', '{}', '{}', {}, {}, {}, {}, {}, {}, {}, {},{},{},{},{},{},{},{},{},{},{}, \
            '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', \"{}\", \"{}\", \"{}\", 1)".format(mParts['messageId'], \
            mParts['sourceComp'], mParts['destComp'], mParts['emailTimestamp'], sParts['deletedFiles'], \
            sParts['deletedFolders'], sParts['modifiedFiles'], sParts['examinedFiles'], sParts['openedFiles'], \
            sParts['addedFiles'], sParts['sizeOfModifiedFiles'], sParts['sizeOfAddedFiles'], sParts['sizeOfExaminedFiles'], sParts['sizeOfOpenedFiles'], \
            sParts['notProcessedFiles'], sParts['addedFolders'], sParts['tooLargeFiles'], sParts['filesWithError'], \
            sParts['modifiedFolders'], sParts['modifiedSymlinks'], sParts['addedSymlinks'], sParts['deletedSymlinks'], \
            sParts['partialBackup'], sParts['dryRun'], sParts['mainOperation'], sParts['parsedResult'], sParts['verboseOutput'], \
            sParts['verboseErrors'], dParts['endTimestamp'], dParts['beginTimestamp'], \
            sParts['duration'], sParts['messages'], sParts['warnings'], sParts['errors'])
                
        globs.log.write(3, 'sqlStmt=[{}]'.format(sqlStmt))
        return sqlStmt

    # Send final email result
    def sendEmail(self, msgHtml, msgText = None, subject = None, sender = None, receiver = None):
        globs.log.write(2, 'sendEmail(msgHtml={}, msgText={}, subject={}, sender={}, receiver={})'.format(msgHtml, msgText, subject, sender, receiver))
        self.connect()

        # Build email message
        msg = MIMEMultipart('alternative')
        if subject is None:
            subject = globs.report.reportOpts['reporttitle']
        msg['Subject'] = subject
        if sender is None:
            sender = globs.opts['outsender']
        msg['From'] = sender
        if receiver is None:
            receiver = globs.opts['outreceiver']
        msg['To'] = receiver
 
        # Add 'Date' header for RFC compliance - See issue #77
        msg['Date'] = email.utils.formatdate(time.time(), localtime=True)

        # Record the MIME types of both parts - text/plain and text/html.
        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart message is best and preferred.
        # So attach text first, then HTML
        if msgText is not None:
            msgPart = MIMEText(msgText, 'plain')
            msg.attach(msgPart)
        if msgHtml is not None:
            msgPart = MIMEText(msgHtml, 'html')
            msg.attach(msgPart)

        # Send the message via SMTP server.
        # The encode('utf-8') was added to deal with non-english character sets in emails. See Issue #26 for details
        globs.log.write(2,'Sending email to [{}]'.format(receiver.split(',')))
        self.server.sendmail(sender, receiver.split(','), msg.as_string().encode('utf-8'))
        return None

    # Send email for errors
    def sendErrorEmail(self, errText):
        globs.log.write(2, 'sendErrorEmail()')
        self.connect()

        # Build email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Duplicati Job Status Error'
        msg['From'] = globs.opts['outsender']
        msg['To'] = globs.opts['outreceiver']
        msg['Date'] = email.utils.formatdate(time.time(), localtime=True)   # Add 'Date' header for RFC compliance - See issue #77

        # Record the MIME type. Only need text type
        msgPart = MIMEText(errText, 'plain')
        msg.attach(msgPart)

        # Send the message via local SMTP server.
        # The encode('utf-8') was added to deal with non-english character sets in emails. See Issue #26 for details
        globs.log.write(2,'Sending error email to [{}]'.format(globs.opts['outreceiver'].split(',')))
        self.server.sendmail(globs.opts['outsender'], globs.opts['outreceiver'].split(','), msg.as_string().encode('utf-8'))

        return None

