#!/usr/bin/python
# Copyright (c) 2012-2015 CORE Security Technologies
#
# This software is provided under under a slightly modified version
# of the Apache Software License. See the accompanying LICENSE file
# for more information.
#
# DCE/RPC lookup sid brute forcer example
#
# Author:
#  Alberto Solino (@agsolino)
#
# Reference for:
#  DCE/RPC [MS-LSAT]

import sys
import logging
import codecs

from impacket import version
from impacket.dcerpc.v5 import transport, lsat, lsad
from impacket.dcerpc.v5.samr import SID_NAME_USE
from impacket.dcerpc.v5.dtypes import MAXIMUM_ALLOWED
from impacket.dcerpc.v5.rpcrt import DCERPCException


class LSALookupSid:
    KNOWN_PROTOCOLS = {
        '139/SMB': (r'ncacn_np:%s[\pipe\lsarpc]', 139),
        '445/SMB': (r'ncacn_np:%s[\pipe\lsarpc]', 445),
        '135/TCP': (r'ncacn_ip_tcp:%s', 135),
        }

    def __init__(self, logger, username, password, domain, protocols = None,
                 hashes = None, maxRid=4000):
        if not protocols:
            protocols = LSALookupSid.KNOWN_PROTOCOLS.keys()

        self.__logger = logger
        self.__username = username
        self.__password = password
        self.__protocols = [protocols]
        self.__maxRid = int(maxRid)
        self.__domain = domain
        self.__lmhash = ''
        self.__nthash = ''
        if hashes is not None:
            self.__lmhash, self.__nthash = hashes.split(':')

    def dump(self, addr):

        logging.info('Brute forcing SIDs at %s' % addr)

        # Try all requested protocols until one works.
        for protocol in self.__protocols:
            protodef = LSALookupSid.KNOWN_PROTOCOLS[protocol]
            port = protodef[1]

            logging.info("Trying protocol %s..." % protocol)
            stringbinding = protodef[0] % addr

            rpctransport = transport.DCERPCTransportFactory(stringbinding)
            rpctransport.set_dport(port)
            if hasattr(rpctransport, 'set_credentials'):
                # This method exists only for selected protocol sequences.
                rpctransport.set_credentials(self.__username, self.__password, self.__domain, self.__lmhash, self.__nthash)

            try:
                self.__logger.success("Brute forcing SIDs (rid:domain:user)")
                self.__bruteForce(rpctransport, self.__maxRid)
            except Exception, e:
                #import traceback
                #print traceback.print_exc()
                logging.critical(str(e))
                raise
            else:
                # Got a response. No need for further iterations.
                break

    def __bruteForce(self, rpctransport, maxRid):
        dce = rpctransport.get_dce_rpc()
        entries = []
        dce.connect()

        # Want encryption? Uncomment next line
        # But make SIMULTANEOUS variable <= 100
        #dce.set_auth_level(ntlm.NTLM_AUTH_PKT_PRIVACY)

        # Want fragmentation? Uncomment next line
        #dce.set_max_fragment_size(32)

        dce.bind(lsat.MSRPC_UUID_LSAT)
        resp = lsat.hLsarOpenPolicy2(dce, MAXIMUM_ALLOWED | lsat.POLICY_LOOKUP_NAMES)
        policyHandle = resp['PolicyHandle']

        resp = lsad.hLsarQueryInformationPolicy2(dce, policyHandle, lsad.POLICY_INFORMATION_CLASS.PolicyAccountDomainInformation)

        domainSid = resp['PolicyInformation']['PolicyAccountDomainInfo']['DomainSid'].formatCanonical()

        soFar = 0
        SIMULTANEOUS = 1000
        for j in range(maxRid/SIMULTANEOUS+1):
            if (maxRid - soFar) / SIMULTANEOUS == 0:
                sidsToCheck = (maxRid - soFar) % SIMULTANEOUS
            else: 
                sidsToCheck = SIMULTANEOUS
 
            if sidsToCheck == 0:
                break

            sids = list()
            for i in xrange(soFar, soFar+sidsToCheck):
                sids.append(domainSid + '-%d' % i)
            try:
                lsat.hLsarLookupSids(dce, policyHandle, sids,lsat.LSAP_LOOKUP_LEVEL.LsapLookupWksta)
            except DCERPCException, e:
                if str(e).find('STATUS_NONE_MAPPED') >= 0:
                    soFar += SIMULTANEOUS
                    continue
                elif str(e).find('STATUS_SOME_NOT_MAPPED') >= 0:
                    resp = e.get_packet()
                else: 
                    raise

            for n, item in enumerate(resp['TranslatedNames']['Names']):
                if item['Use'] != SID_NAME_USE.SidTypeUnknown:
                    self.__logger.results("%d: %s\\%s (%s)" % (soFar+n, resp['ReferencedDomains']['Domains'][item['DomainIndex']]['Name'], item['Name'], SID_NAME_USE.enumItems(item['Use']).name))
            soFar += SIMULTANEOUS

        dce.disconnect()

        return entries
