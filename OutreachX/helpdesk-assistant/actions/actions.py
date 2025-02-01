import logging
from typing import Dict, Text, Any, List
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher, Action
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.events import AllSlotsReset, SlotSet
from actions.snow import SnowAPI
import random
import string
import os 
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
import re
# from database.db_helper import AzureTableHelper
from azure.data.tables import TableClient, TableServiceClient
from uuid import uuid4
from flask import Flask, request, jsonify
from flask_cors import CORS  # Import CORS
import logging

load_dotenv()


logger = logging.getLogger(__name__)
vers = "vers: 0.1.0, date: Apr 2, 2020"
logger.debug(vers)

snow = SnowAPI()
localmode = snow.localmode
logger.debug(f"Local mode: {snow.localmode}")

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
print("Hello World")

class ActionAskEmail(Action):
    def name(self) -> Text:
        return "action_ask_email"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        if tracker.get_slot("previous_email"):
            dispatcher.utter_message(template=f"utter_ask_use_previous_email",)
        else:
            dispatcher.utter_message(template=f"utter_ask_email")
        return []


def _validate_email(
    value: Text,
    dispatcher: CollectingDispatcher,
    tracker: Tracker,
    domain: Dict[Text, Any],
) -> Dict[Text, Any]:
    """Validate email is in ticket system."""
    if not value:
        return {"email": None, "previous_email": None}
    elif isinstance(value, bool):
        value = tracker.get_slot("previous_email")

    if localmode:
        return {"email": value}

    results = snow.email_to_sysid(value)
    caller_id = results.get("caller_id")

    if caller_id:
        return {"email": value, "caller_id": caller_id}
    elif isinstance(caller_id, list):
        dispatcher.utter_message(template="utter_no_email")
        return {"email": None}
    else:
        dispatcher.utter_message(results.get("error"))
        return {"email": None}


class ValidateOpenIncidentForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_open_incident_form"

    def validate_email(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate email is in ticket system."""
        return _validate_email(value, dispatcher, tracker, domain)

    def validate_priority(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate priority is a valid value."""

        if value.lower() in snow.priority_db():
            return {"priority": value}
        else:
            dispatcher.utter_message(template="utter_no_priority")
            return {"priority": None}
        
    def validate_incident_title(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate the incident title slot."""
        if not value or len(value.strip()) == 0:
            dispatcher.utter_message(text="The incident title cannot be empty. Please provide a valid title.")
            return {"incident_title": None}
        return {"incident_title": value.strip()}



class ActionOpenIncident(Action):
    def name(self) -> Text:
        return "action_open_incident"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Create an incident and return details or
        if localmode return incident details as if incident
        was created
        """

        priority = tracker.get_slot("priority")
        email = tracker.get_slot("email")
        problem_description = tracker.get_slot("problem_description")
        incident_title = tracker.get_slot("incident_title")
        confirm = tracker.get_slot("confirm")
        if not confirm:
            dispatcher.utter_message(
                template="utter_incident_creation_canceled"
            )
            return [AllSlotsReset(), SlotSet("previous_email", email)]

        if localmode:
            message = (
                f"An incident with the following details would be opened "
                f"if ServiceNow was connected:\n"
                f"email: {email}\n"
                f"problem description: {problem_description}\n"
                f"title: {incident_title}\npriority: {priority}"
            )
        else:
            snow_priority = snow.priority_db().get(priority)
            response = snow.create_incident(
                description=problem_description,
                short_description=incident_title,
                priority=snow_priority,
                email=email,
            )
            incident_number = (
                response.get("content", {}).get("result", {}).get("number")
            )
            if incident_number:
                message = (
                    f"Successfully opened up incident {incident_number} "
                    f"for you. Someone will reach out soon."
                )
            else:
                message = (
                    f"Something went wrong while opening an incident for you. "
                    f"{response.get('error')}"
                )
        dispatcher.utter_message(message)
        return [AllSlotsReset(), SlotSet("previous_email", email)]


class IncidentStatusForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_incident_status_form"

    def validate_email(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate email is in ticket system."""
        return _validate_email(value, dispatcher, tracker, domain)


class ActionCheckIncidentStatus(Action):
    def __init__(self):
        self.db = AzureTableHelper()

    def name(self) -> Text:
        return "action_check_incident_status"

    def get_access_token(self) -> str:
        """
        Retrieve an access token using OAuth2 client credentials.
        """
        # Authentication details
        client_id = os.getenv("AZURE_CLIENT_ID")
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        tenant_id = os.getenv("AZURE_TENANT_ID")
        resource = "https://graph.microsoft.com/"

        # Get access token
        auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "resource": resource,
        }
        auth_response = requests.post(auth_url, data=auth_data)
        auth_response_data = auth_response.json()
        if "access_token" not in auth_response_data:
            raise Exception("Failed to retrieve access token.")
        return auth_response_data["access_token"]

    def fetch_messages(self, email: str, ticket_number: str, access_token: str) -> List[Dict]:
        """
        Fetch emails related to the given ticket number from the Microsoft Graph API.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        url = f"https://graph.microsoft.com/v1.0/users/{email}/messages"
        params = {
            "$filter": f"contains(subject, '{ticket_number}')",
            "$select": "subject,bodyPreview,conversationId,receivedDateTime",
        }

        messages = []
        while url:
            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                messages.extend(data.get("value", []))

                # Handle pagination
                url = data.get("@odata.nextLink", None)
                params = None  # After the first request, no need for query parameters
            else:
                error_message = response.json().get("error", {}).get("message", "Unknown error")
                raise Exception(f"Failed to fetch emails. Status code: {response.status_code}. Error: {error_message}")

        return messages

    def check_ticket_status(self, email: str, ticket_number: str) -> tuple:
        try:
            # Get access token and set up headers
            access_token = self.get_access_token()
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Get messages related to the specific ticket number
            url = f"https://graph.microsoft.com/v1.0/users/{email}/messages"
            params = {
                "$filter": f"contains(subject,'{ticket_number}')",
                "$select": "subject,body,bodyPreview,conversationId,receivedDateTime",
                "$top": 25
            }

            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                messages = response.json().get('value', [])
                
                if not messages:
                    return "Open", ""
                
                # Sort messages by receivedDateTime in descending order
                messages.sort(
                    key=lambda x: x.get('receivedDateTime', ''),
                    reverse=True
                )
                
                # Get the full subject from the first message and clean it
                full_subject = messages[0].get('subject', '')
                # Remove 'Re:' prefix and any leading/trailing whitespace
                full_subject = full_subject.replace('Re:', '').strip()
                
                # Keywords that indicate a ticket is closed
                closed_keywords = [
                    'resolved', 'completed', 'fixed', 'closed', 'done',
                    'issue resolved', 'problem fixed', 'ticket closed'
                ]
                
                # Keywords that indicate a ticket is in progress
                progress_keywords = [
                    'working on', 'in progress', 'investigating', 
                    'looking into', 'will check', 'checking'
                ]
                
                # Check all messages in the conversation
                for message in messages:
                    body = message.get('bodyPreview', '').lower()
                    message_subject = message.get('subject', '').lower()
                    
                    # Check for closed status keywords
                    if any(keyword in body or keyword in message_subject 
                          for keyword in closed_keywords):
                        return "Closed", full_subject
                    
                    # Check for in progress keywords
                    if any(keyword in body or keyword in message_subject 
                          for keyword in progress_keywords):
                        return "In Progress", full_subject
                
                # If there are multiple messages but no status keywords, mark as in progress
                if len(messages) > 1:
                    return "In Progress", full_subject
                
                # If we've gotten here and found no status indicators, mark as open
                return "Open", full_subject
            
            else:
                error_message = response.json().get('error', {}).get('message', 'Unknown error')
                raise Exception(f"Failed to fetch emails. Status code: {response.status_code}. Error: {error_message}")
                
        except Exception as e:
            raise Exception(f"Error checking ticket status: {str(e)}")

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        email = tracker.get_slot("email")
        ticket_number = tracker.get_slot("ticket_number")
        
        try:
            # If no ticket number provided, get the most recent ticket
            if not ticket_number:
                access_token = self.get_access_token()
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                
                url = f"https://graph.microsoft.com/v1.0/users/{email}/messages"
                params = {
                    "$select": "subject,bodyPreview,conversationId",
                    "$top": 1,
                    "$orderby": "createdDateTime desc"
                }
                
                response = requests.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    messages = response.json().get('value', [])
                    if messages:
                        # Get the ticket number from the most recent email subject
                        recent_subject = messages[0].get('subject', '')
                        ticket_id = recent_subject.split(':')[0].strip()
                        
                        # Check status of the most recent ticket
                        status, full_subject = self.check_ticket_status(email, ticket_id)
                        
                        status_messages = {
                            "Open": f'Your most recent incident "{full_subject}" is currently [red]Open[/red]. No responses have been received yet.',
                            "In Progress": f'Your most recent incident "{full_subject}" is [yellow]In Progress[/yellow]. Our team is working on it.',
                            "Closed": f'Your most recent incident "{full_subject}" has been [green]Closed[/green]. The issue has been resolved.'
                        }
                        
                        # Send status message with buttons
                        dispatcher.utter_message(
                            text=status_messages.get(status, "Unable to determine status."),
                            buttons=[
                                {"title": "Check Another Ticket", "payload": "/check_different_ticket"},
                                {"title": "That's All", "payload": "/thank_you"}
                            ]
                        )
                        return []
                    
                # If no recent tickets found or error occurred, ask for ticket number with option to check recent
                dispatcher.utter_message(
                    text="Please provide your ticket number to check the status.",
                    buttons=[
                        {"title": "Check Recent Ticket", "payload": "/check_recent_ticket"}
                    ]
                )
                return [SlotSet("ticket_number", None)]
                
            else:
                # If ticket number is provided, proceed with normal status check
                ticket_id = ticket_number.split(':')[0].strip()
                status, full_subject = self.check_ticket_status(email, ticket_id)
                
                status_messages = {
                    "Open": f'Your incident "{full_subject}" is currently [red]Open[/red]. No responses have been received yet.',
                    "In Progress": f'Your incident "{full_subject}" is [yellow]In Progress[/yellow]. Our team is working on it.',
                    "Closed": f'Your incident "{full_subject}" has been [green]Closed[/green]. The issue has been resolved.'
                }
                
                # Send status message with option to check another
                dispatcher.utter_message(
                    text=status_messages.get(status, "Unable to determine status."),
                    buttons=[
                        {"title": "Check Another Ticket", "payload": "/check_different_ticket"},
                        {"title": "That's All", "payload": "/thank_you"}
                    ]
                )
                return [SlotSet("ticket_number", None)]
                
        except Exception as e:
            dispatcher.utter_message(text=f"Error checking incident status: {str(e)}")
            return [SlotSet("ticket_number", None)]

    
class AzureTableHelper:
    def __init__(self):
        # Use your Azure credentials (connection string)
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.table_name = "IncidentsTable"
        self.table_client = TableClient.from_connection_string(
            conn_str=self.connection_string,
            table_name=self.table_name
        )
    
    def _create_table_if_not_exists(self):
        """Create table if it doesn't exist."""
        table_service_client = TableServiceClient.from_connection_string(
            conn_str=self.connection_string
        )
        try:
            table_service_client.create_table_if_not_exists(self.table_name)
        except Exception as e:
            print(f"Error creating table: {str(e)}")
            raise

    def insert_incident(self, incident_data: Dict[Text, Any]) -> None:
        """Insert an incident into Azure Table Storage."""
        try:
            self.table_client.create_entity(entity=incident_data)
            print(f"Incident inserted: {incident_data}")
        except Exception as e:
            print(f"Error inserting incident: {e}")
            raise

    def fetch_tickets_by_user(self, email: str) -> List[Dict[str, Any]]:
        """
        Fetch all tickets created by a specific user (Sender field).
        """
        print("Email:", email)
        try:
            filter_query = f"Sender eq '{email}'"
            entities = self.table_client.query_entities(query_filter=filter_query)
            print("entities:", entities)
            tickets = []
            for entity in entities:
                tickets.append({
                    "PartitionKey": entity["PartitionKey"],
                    "RowKey": entity["RowKey"],
                    "Sender": entity.get("Sender", ""),
                    "Recipient": entity.get("Recipient", ""),
                    "Priority": entity.get("Priority", ""),
                    "Description": entity.get("Description", ""),
                    "Title": entity.get("Title", ""),
                    "CreatedDate": entity.get("CreatedDate", ""),
                })
            print(tickets)
            return tickets
        except Exception as e:
            print(f"Error fetching tickets: {e}")
            raise


class ActionFetchUserTickets(Action):
    def name(self) -> str:
        return "action_fetch_user_tickets"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict):
        user_email = "rahul@wintellisys.com"  # Default email for testing
        
        if not user_email:
            dispatcher.utter_message(text="No email address provided. Please try again.")
            return []

        # Fetch tickets for the user
        azure_helper = AzureTableHelper()
        try:
            tickets = azure_helper.fetch_tickets_by_user(user_email)

            if not tickets:
                dispatcher.utter_message(text=f"No tickets found for {user_email}.")
                return []

            # Sort tickets by CreatedDate (descending order)
            sorted_tickets = sorted(
                tickets, key=lambda x: x.get("CreatedDate", ""), reverse=True
            )

            # Respond with sorted tickets
            dispatcher.utter_message(
                json_message={"tickets": sorted_tickets}  # Send to frontend or display
            )
        
        except Exception as e:
            dispatcher.utter_message(text=f"Error fetching tickets: {str(e)}")
        
        return []



# Initialize Flask app and set up CORS to allow requests
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'  # Allow any origin
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("Webhook called")  # Log when the webhook is called
    try:
        data = request.json  # Fetch the POSTed JSON data
        logger.info(f"Data received: {data}")
        
        # Ensure correct action
        if data.get("next_action") == "action_fetch_user_tickets":
            email = data.get("tracker", {}).get("slots", {}).get("email", "")
            if not email:
                return jsonify({"status": "error", "message": "Email not provided"})

            # Fetch tickets using AzureTableHelper (adjust logic if needed)
            azure_helper = AzureTableHelper()
            tickets = azure_helper.fetch_tickets_by_user(email)

            # Return tickets in response
            return jsonify({
                "status": "success",
                "tickets": tickets  # Return fetched ticket data
            })
        
        # Handle invalid action
        return jsonify({"status": "error", "message": "Invalid action"})
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")  # Log the error
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(port=5055)


db = AzureTableHelper()

class ActionSubmitIncident(Action):
    def __init__(self):
        self.db = AzureTableHelper()

    def name(self) -> Text:
        return "action_submit_incident"

    def generate_ticket_number(self) -> str:
        random_digits = ''.join(random.choices(string.digits, k=10))
        return f"TKT{random_digits}"

    def get_access_token(self) -> str:
        # Authentication details for email sending (Azure AD OAuth 2.0)
        client_id = os.getenv("AZURE_CLIENT_ID")
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        tenant_id = os.getenv("AZURE_TENANT_ID")
        resource = "https://graph.microsoft.com/"

        # Get access token
        auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "resource": resource,
        }
        auth_response = requests.post(auth_url, data=auth_data)
        auth_response_data = auth_response.json()
        return auth_response_data["access_token"]

    def send_email_incident(self, sender_email: str, priority: str, 
                          problem_description: str, incident_title: str) -> str:
        ticket_number = self.generate_ticket_number()
        
        try:
            access_token = self.get_access_token()
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            email_subject = f"{ticket_number}: {incident_title}"
            email_content = f"""
Hi,

This is a {priority} priority issue.

Description: {problem_description}.

Best Regards,
{sender_email}
            """

            url = f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail"
            email_message = {
                "message": {
                    "subject": email_subject,
                    "body": {
                        "contentType": "Text",
                        "content": email_content
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": os.getenv("HELPDESK_EMAIL")
                            }
                        }
                    ]
                },
                "saveToSentItems": "true"
            }

            response = requests.post(url, headers=headers, json=email_message)
            if response.status_code != 202:
                raise Exception(f"Failed to send email. Status code: {response.status_code}")
            
            return ticket_number
            
        except Exception as e:
            raise Exception(f"Failed to send email: {str(e)}")

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        email = tracker.get_slot("email")
        priority = tracker.get_slot("priority")
        problem_description = tracker.get_slot("problem_description")
        incident_title = tracker.get_slot("incident_title")
        confirm = tracker.get_slot("confirm")

        if not incident_title:  # Check if incident_title is provided
            dispatcher.utter_message(text="Please provide the incident title.")
            return [SlotSet("requested_slot", "incident_title")]

        if not confirm:
            dispatcher.utter_message(text="Incident creation canceled.")
            return [
                SlotSet("priority", None),
                SlotSet("problem_description", None),
                SlotSet("incident_title", None),
                SlotSet("confirm", None),
                SlotSet("requested_slot", None)
            ]
        
        try:
            ticket_number = self.send_email_incident(
                sender_email=email,
                priority=priority,
                problem_description=problem_description,
                incident_title=incident_title
            )
            
            # Prepare incident data for Azure Table Storage
            incident_data = {
                "PartitionKey": ticket_number,
                "RowKey": str(uuid4()),
                "Sender": email,
                "Recipient": os.getenv("HELPDESK_EMAIL"),
                "Priority": priority,
                "Description": problem_description,
                "Title": incident_title,
                "CreatedDate": datetime.utcnow().isoformat()
            }

            # Store in Azure Table
            self.db.insert_incident(incident_data)
            dispatcher.utter_message(
                text=f"Incident created successfully. Ticket number: {ticket_number}"
            )

        except Exception as e:
            dispatcher.utter_message(text=f"Error creating incident: {str(e)}")

        return [
            SlotSet("priority", None),
            SlotSet("problem_description", None),
            SlotSet("incident_title", None),
            SlotSet("confirm", None),
            SlotSet("requested_slot", None)
        ]

    

class ValidateIncidentStatusForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_incident_status_form"

    def validate_ticket_number(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        """Validate ticket_number value."""
        # Add any validation logic here
        if slot_value and isinstance(slot_value, str):
            return {"ticket_number": slot_value.strip()}
        return {"ticket_number": None}
    
class ActionResetIncidentForm(Action):
    def name(self) -> Text:
        return "action_reset_incident_form"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        # Reset all slots related to incident creation
        return [
            SlotSet("email", None),
            SlotSet("priority", None),
            SlotSet("problem_description", None),
            SlotSet("incident_title", None),
            SlotSet("confirm", None),
            SlotSet("requested_slot", None)
        ]