from pymisp import *
import requests
import base64

"""
Helper functions for MISP playbooks

"""

def pb_get_urlscan(misp, urlscan_url, urlscan_apikey, urlscan_mapping, misp_event, source_url, url_object, phishing_object, attribute_tags):
    '''
    Query URLscan for the scan results of a given URL, create MISP attributes and objects and return the results
    We can use the MISP URLscan module but for our playbook we only require a check of the results, not a submit.
    Also we need a bit more flexiblity in parsing the results.

    :param misp: MISP object
    :param urlscan_url: URLscan endpoint
    :param urlscan_apikey: URLscan API key
    :param urlscan_mapping: list of values for which to create attributes/objects
    :param misp_event: MISP event
    :param source_url: Search URLscan for results for this URL
    :param url_object: corresponding URL object in MISP
    :param phishing_object: corresponding phishing object in MISP
    :param attribute_tags: tags to add for attributes 

    '''

    # Required by URLscan to submit the URL
    replace_urlscan = ["+", "-", "=", "&&", "||", ">", "<", "!", "(", ")", "{", "}", "[", "]", "^", "~", "*", "?", ":", "/"]
    tag_urlscan_prefix = "urlscan"
    url = source_url.strip()
    for k in replace_urlscan:
        url = url.replace(k, "\{}".format(k))
    enrichment = []
    headers = {"API-Key": urlscan_apikey, "Content-Type": "application/json", "Cache-Control": "no-cache"}
    result = requests.get("{}/?q=page.url.keyword:{}".format(urlscan_url, url), headers=headers)

    if result.status_code == 200 and result.json().get("total") > 0:
        for el in result.json().get("results"):
            screenshot_data = requests.get(el["screenshot"])
            enrichment.append({
                    "time": el["task"].get("time", False),
                    "source": el["task"].get("source", False),
                    "country": el["page"].get("country", False),
                    "server": el["page"].get("server", "Unknown").strip(),
                    "ip": el["page"].get("ip", False),
                    "title": el["page"].get("title", "").strip(),
                    "url": el["page"]["url"],
                    "ptr": el["page"].get("ptr", False),
                    "tlsIssuer": el["page"].get("tlsIssuer", False),
                    "asnname": el["page"].get("asnname", False),
                    "asn": el["page"].get("asn", False),
                    "status": el["page"]["status"],
                    "result": el["result"],
                    "screenshot": el["screenshot"],
                    "screenshot_data": screenshot_data
            })

        for enriched in enrichment:
            if "asn" in urlscan_mapping and "asn" in enriched and "asnname" in enriched:
                # First check if we already have this object
                already_there = False
                already_there_result = misp.search("objects", value=[enriched["asn"], enriched["asnname"]], eventid=misp_event.id, pythonify=True)
                for object_there in already_there_result:
                    if object_there.name == "asn":
                        for attribute in object_there.attributes:
                            if attribute.object_relation == "asn" and "AS{}".format(attribute.value) == enriched["asn"]:
                                already_there = True
                # Avoid cluttering the event with additional objects.
                # Ideally we should add a reference to the existing object.
                if not already_there:
                    asn_object = MISPObject("asn")
                    tags = pb_get_misp_tags(["{}={}".format(tag_urlscan_prefix, "asn")])
                    asn_object = pb_add_objectattr_from_dict(enriched, asn_object, "asnname", "description", tags=tags)
                    asn_object = pb_add_objectattr_from_dict(enriched, asn_object, "asn", "asn", tags=tags)
                    try:
                        asn_object_misp = misp.add_object(misp_event.uuid, asn_object, pythonify=True)
                        misp.add_object_reference(url_object.add_reference(asn_object_misp.uuid, "linked-to"))
                    except Exception as e:
                        print("asnname", e)

            if "ip" in urlscan_mapping and "ip" in enriched and "ptr-record" in enriched:
                # First check if we already have this object
                already_there = False
                already_there_result = misp.search("objects", value=[enriched["ptr"], enriched["ip"]], eventid=misp_event.id, pythonify=True)                
                for object_there in already_there_result:
                    if object_there.name == "dns-record":
                        for attribute in object_there.attributes:
                            if attribute.object_relation == "queried-domain" and attribute.value == enriched["ip"]:
                                already_there = True
                # Avoid cluttering the event with additional objects.
                # Ideally we should add a reference to the existing object.                                
                if not already_there:                
                    dns_object = MISPObject("dns-record")
                    tags = pb_get_misp_tags(["{}={}".format(tag_urlscan_prefix, "dns-record")])
                    dns_object = pb_add_objectattr_from_dict(enriched, dns_object, "ptr", "ptr-record", attribute_tags["ip"] + tags, -1, True)
                    dns_object = pb_add_objectattr_from_dict(enriched, dns_object, "ip", "queried-domain", attribute_tags["ip"] + tags, -1, True)
                    try:
                        dns_object_misp = misp.add_object(misp_event.uuid, dns_object, pythonify=True)
                        #if "errors" not in dns_object_misp:
                        misp.add_object_reference(url_object.add_reference(dns_object_misp.uuid, "resolved-to"))
                    except Exception as e:
                        print("dns-record", e)

            if "country" in urlscan_mapping and "country" in enriched:
                # No need to check for "already there", MISP prevents double attributes of same type, category and value
                attribute = MISPAttribute()
                attribute.category = "External analysis"
                attribute.type = "text"
                attribute.value = "country: {}".format(enriched["country"])
                attribute.to_ids = False
                attribute.disable_correlation = False
                attribute.tags = pb_get_misp_tags(["{}={}".format(tag_urlscan_prefix, "country")])
                try:
                    country_attribute = misp.add_attribute(misp_event.uuid, attribute, pythonify=True)
                    if "errors" not in country_attribute:
                        misp.add_object_reference(url_object.add_reference(country_attribute.uuid, "located"))
                except Exception as e:
                    print("country", e)

            if "tlsIssuer" in urlscan_mapping and "tlsIssuer" in enriched and enriched["tlsIssuer"] != False:
                # No need to check for "already there", MISP prevents double attributes of same type, category and value                
                attribute = MISPAttribute()
                attribute.category = "External analysis"
                attribute.type = "text"
                attribute.value = "tlsIssuer: {}".format(enriched["tlsIssuer"])
                attribute.to_ids = False
                attribute.disable_correlation = False
                attribute.tags = pb_get_misp_tags(["{}={}".format(tag_urlscan_prefix, "tlsIssuer")])                
                try:
                    tls_attribute = misp.add_attribute(misp_event.uuid, attribute, pythonify=True)
                    if "errors" not in tls_attribute:
                        misp.add_object_reference(url_object.add_reference(tls_attribute.uuid, "related-to"))
                except Exception as e:
                    print("tlsIssuer", e)

            if "server" in urlscan_mapping and "server" in enriched:
                # No need to check for "already there", MISP prevents double attributes of same type, category and value
                attribute = MISPAttribute()
                attribute.category = "External analysis"
                attribute.type = "text"
                attribute.value = "server: {}".format(enriched["server"])
                attribute.to_ids = False
                attribute.disable_correlation = False
                attribute.tags = pb_get_misp_tags(["{}={}".format(tag_urlscan_prefix, "server")])                
                try:
                    server_attribute = misp.add_attribute(misp_event.uuid, attribute, pythonify=True)
                    if "errors" not in server_attribute:
                        misp.add_object_reference(url_object.add_reference(server_attribute.uuid, "found-on"))
                except Exception as e:
                    print("server", e)

            if "source_time" in urlscan_mapping and "source" in enriched and "time" in enriched:
                # No need to check for "already there", MISP prevents double attributes of same type, category and value                
                attribute = MISPAttribute()
                attribute.category = "External analysis"
                attribute.type = "text"
                attribute.value = "URLscan.io submit: {} ({})".format(enriched["source"], enriched["time"])
                attribute.to_ids = False
                attribute.disable_correlation = True
                attribute.tags = pb_get_misp_tags(["{}={}".format(tag_urlscan_prefix, "source")])                
                try:
                    source_attribute = misp.add_attribute(misp_event.uuid, attribute, pythonify=True)
                    if "errors" not in source_attribute:
                        misp.add_object_reference(url_object.add_reference(source_attribute.uuid, "analyzed-with"))
                except Exception as e:
                    print("source_time", e)

            if "result" in enriched:
                # First check if it's already there
                comment = "URLscan.io scan result for {}".format(source_url)
                already_there = misp.search("attributes", value=enriched["result"], uuid=misp_event.uuid, comment=comment, to_ids=False, type="link", category="External analysis", limit=1, pythonify=True)
                if len(already_there) < 1:
                    attribute = MISPAttribute()
                    attribute.category = "External analysis"
                    attribute.type = "link"
                    attribute.value = enriched["result"]
                    attribute.to_ids = False
                    attribute.comment = "URLscan.io scan result for {}".format(source_url)
                    attribute.disable_correlation = True
                    attribute.tags = pb_get_misp_tags(["{}={}".format(tag_urlscan_prefix, "result")])                    
                    try:
                        urlscan_result_attribute = misp.add_attribute(misp_event.uuid, attribute, pythonify=True)
                        if "errors" not in urlscan_result_attribute:
                            misp.add_object_reference(url_object.add_reference(urlscan_result_attribute.uuid, "analyzed-with"))
                    except Exception as e:
                        print("result", e)

            if "screenshot" in enriched:
                # First check if it's already there
                comment = "URLscan.io screenshot for {}".format(source_url)
                already_there = misp.search("attributes", value=enriched["screenshot"], uuid=misp_event.uuid, comment=comment, to_ids=False, type="link", category="External analysis", limit=1, pythonify=True)
                if len(already_there) < 1:
                    attribute = MISPAttribute()
                    attribute.category = "External analysis"
                    attribute.type = "link"
                    attribute.value = enriched["screenshot"]
                    attribute.to_ids = False
                    attribute.comment = comment
                    attribute.disable_correlation = True
                    attribute.tags = pb_get_misp_tags(["{}={}".format(tag_urlscan_prefix, "screenshot")])                                        
                    try:
                        urlscan_screenshot_attribute = misp.add_attribute(misp_event.uuid, attribute, pythonify=True)
                        if "errors" not in urlscan_screenshot_attribute:
                            misp.add_object_reference(url_object.add_reference(urlscan_screenshot_attribute.uuid, "analyzed-with"))
                            comment = "{} for {}".format(enriched["screenshot"], source_url)
                            phishing_object.add_attribute("screenshot", value="screenshot.png", data=base64.b64encode(enriched["screenshot_data"].content).decode('utf-8'), tags=pb_get_misp_tags(["{}={}".format(tag_urlscan_prefix, "screenshot")], []), comment=comment)
                            misp.update_object(phishing_object)
                    except Exception as e:
                        print("screenshot", e)

            try:
                if "ip" in enriched:
                    #attributes = misp.get_object("24606215-f6a7-4850-955c-4e92c9009755", pythonify=True)
                    already_there = False
                    for attr in url_object.Attribute:
                        if attr.object_relation == "ip" and attr.value == enriched["ip"]:
                            already_there = True
                    if not already_there:                        
                        url_object.add_attribute("ip", enriched["ip"], tags=pb_get_misp_tags(["{}={}".format(tag_urlscan_prefix, "ip")]) + attribute_tags["ip"], comment=source_url)
                if "title" in enriched and len(enriched["title"]) > 0:
                    already_there = False
                    for attr in url_object.Attribute:
                        if attr.object_relation == "text" and attr.value == "Site title: {}".format(enriched["title"]):
                            already_there = True
                    if not already_there:
                        url_object.add_attribute("text", "Site title: {}".format(enriched["title"]), tags=pb_get_misp_tags(["{}={}".format(tag_urlscan_prefix, "sitetitle")]), comment=source_url)
                misp.update_object(url_object)
            except Exception as e:
                print("ip_title", e)
        return enrichment
    else:
        return False


def pb_print_object_definition(misp, object_template):
    '''
    Print the raw object template

    :param misp: MISP object
    :param object_template: which object template to return
    '''

    if object_template:
        object_definition = misp.get_raw_object_template(object_template)  # get_raw_object_template does not support pythonify
        if "errors" not in object_definition:
            from prettytable import PrettyTable
            object_definition_table = PrettyTable()
            object_definition_table.title = "MISP object definition for '{}'".format(object_template)
            object_definition_table.field_names = ["Object attribute name", "Description", "MISP attribute type", "Multiple allowed?"]
            object_definition_table.align["Object attribute name"] = "l"
            object_definition_table.align["Description"] = "l"
            object_definition_table.align["MISP attribute type"] = "l"
            object_definition_table.sortby = "Object attribute name"
            object_definition_table.border = True

            for attribute in object_definition["attributes"]:
                attribute_details = object_definition["attributes"][attribute]
                multiple = False
                if attribute_details.get("multiple", False):
                    multiple = True
                object_definition_table.add_row([attribute, attribute_details["description"][:50], attribute_details["misp-attribute"], multiple])
            print(object_definition_table)
            if "required" in object_definition:
                print("required", object_definition["required"])
            elif "requiredOneOf" in object_definition:
                print("requiredOneOf", object_definition["requiredOneOf"])
        else:
            print("Error: {} for template {}".format(object_definition["errors"][1]["message"], object_template))
            return False
    else:
        print("No object template supplied")
        return False


def pb_add_objectattr_from_dict(playbook_dict, playbook_object, playbook_attr, object_type, tags=[], distribution=-1, force_toids_false=False):
    '''
    Find a match between fields provided in the playbook and the fieldnames part of the object and the add it as an attribute
    to the object

    :param playbook_dict: dictionary containing the playbook fields
    :param playbook_object: object from the playbook that requires changes
    :param playbook_attr: field in the playbook
    :param object_type: field in the object
    :param tags: tags to add to the attribute
    :param distribution: override distribution level (default -1)
    :param force_toids_false: override the IDS setting and set to false
    '''

    if playbook_attr in playbook_dict and playbook_dict[playbook_attr] is not None and len(playbook_dict[playbook_attr]) > 0:
        if type(playbook_dict[playbook_attr]) == list:
            for el in playbook_dict[playbook_attr]:
                if distribution > -1:
                    if force_toids_false:
                        playbook_object.add_attribute(object_type, el, to_ids=False, tags=tags, distribution=distribution)
                    else:
                        playbook_object.add_attribute(object_type, el, tags=tags, distribution=distribution)
                else:
                    if force_toids_false:
                        playbook_object.add_attribute(object_type, el, to_ids=False, tags=tags)
                    else:
                        playbook_object.add_attribute(object_type, el, tags=tags)
        else:
            if distribution > -1:
                if force_toids_false:
                    playbook_object.add_attribute(object_type, playbook_dict[playbook_attr], to_ids=False, tags=tags, distribution=distribution)
                else:
                    playbook_object.add_attribute(object_type, playbook_dict[playbook_attr], tags=tags, distribution=distribution)
            else:
                if force_toids_false:
                    playbook_object.add_attribute(object_type, playbook_dict[playbook_attr], to_ids=False, tags=tags)
                else:
                    playbook_object.add_attribute(object_type, playbook_dict[playbook_attr], tags=tags)
    return playbook_object


def pb_get_misp_tags(tags=[], local_tags=[]):
    '''
    Get a list of MISP tags based on a Python list

    :param misp: MISP object
    :param object_template: which object template to return
    '''
    misp_tags = []
    for el in tags:
        t = MISPTag()
        t.name = el
        t.local = False
        misp_tags.append(t)

    for el in local_tags:
        t = MISPTag()
        t.name = el
        t.local = True
        misp_tags.append(t)
    return misp_tags
