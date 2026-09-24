"""
Seed script for Beyond2U IT Helpdesk.

Creates default SLA policies, technical skills matrix, standard master admin,
10 technician accounts, 10 client accounts, and 5 realistic support tickets.
"""

import logging
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.extensions import db
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.skill import Skill, TechnicianSkill
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus
from app.services.tickets import TicketService

logger = logging.getLogger(__name__)


def run_seed(app=None):
    """Seed initial reference data, 10 technicians, 10 clients, and 5 tickets."""
    print("Starting database seeding...")

    # 1. Default Organization
    org = Organization.query.filter_by(name="Beyond2U Sdn Bhd").first()
    if not org:
        org = Organization(
            name="Beyond2U Sdn Bhd",
            description="Beyond2U Headquarters",
        )
        db.session.add(org)
        db.session.flush()
        print("  - Created default organization: Beyond2U Sdn Bhd")

    # 2. SLA Policies
    sla_configs = [
        {"priority": TicketPriority.CRITICAL.value, "resolution_hours": 4.0, "warning_threshold_pct": 75},
        {"priority": TicketPriority.HIGH.value, "resolution_hours": 8.0, "warning_threshold_pct": 75},
        {"priority": TicketPriority.MEDIUM.value, "resolution_hours": 24.0, "warning_threshold_pct": 75},
        {"priority": TicketPriority.LOW.value, "resolution_hours": 72.0, "warning_threshold_pct": 80},
    ]

    for cfg in sla_configs:
        policy = SLAPolicy.query.filter_by(priority=cfg["priority"]).first()
        if not policy:
            policy = SLAPolicy(
                priority=cfg["priority"],
                resolution_hours=cfg["resolution_hours"],
                warning_threshold_pct=cfg["warning_threshold_pct"],
                is_active=True,
            )
            db.session.add(policy)
            print(f"  - Created SLA Policy: {cfg['priority']} ({cfg['resolution_hours']}h)")

    # 3. IT Skills Matrix (6 Categories)
    skills_data = [
        {"name": "Hardware Repair & Maintenance", "category": TicketCategory.HARDWARE.value, "description": "Laptops, desktops, monitors, peripherals, component replacement"},
        {"name": "Network & Connectivity", "category": TicketCategory.NETWORK.value, "description": "VPN, Wi-Fi, Ethernet, routers, switches, firewall rules, IP allocation"},
        {"name": "Software & Applications", "category": TicketCategory.SOFTWARE.value, "description": "OS installation, Office 365, browser issues, drivers, licensed software"},
        {"name": "Access & Accounts Management", "category": TicketCategory.ACCESS_ACCOUNTS.value, "description": "Password resets, Active Directory, MFA tokens, permission requests, SSO"},
        {"name": "Email & Communication Services", "category": TicketCategory.EMAIL_COMMUNICATION.value, "description": "Outlook, Teams, Exchange server, email encryption, spam filtering"},
        {"name": "Server & Infrastructure Systems", "category": TicketCategory.SERVER_INFRASTRUCTURE.value, "description": "PostgreSQL, Linux, Windows Server, Docker, backup recovery, disk storage"},
    ]

    skill_objs = {}
    for s_data in skills_data:
        skill = Skill.query.filter_by(name=s_data["name"]).first()
        if not skill:
            skill = Skill(
                name=s_data["name"],
                category=s_data["category"],
                description=s_data["description"],
                is_active=True,
            )
            db.session.add(skill)
            db.session.flush()
            print(f"  - Created Skill: {s_data['name']}")
        skill_objs[s_data["category"]] = skill

    # 4. Master Administrator
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        admin_user = User(
            organization_id=org.id,
            username="admin",
            email="admin@dummy.com",
            first_name="System",
            last_name="Administrator",
            role=UserRole.ADMIN,
            phone_number="+60 3-2170 8888",
            job_title="IT Director",
            department="IT Management & Governance",
            company_name="Beyond2U Sdn Bhd",
            address="Level 12, Menara Beyond2U, Kuala Lumpur",
            is_active=True,
            is_available=True,
        )
        admin_user.set_password("AdminPassword123!")
        db.session.add(admin_user)
        db.session.flush()
        print("  - Created Master Admin: admin (admin@dummy.com)")
    else:
        admin_user.email = "admin@dummy.com"
        admin_user.set_password("AdminPassword123!")

    # 5. 10 Technicians
    technicians_data = [
        {
            "username": "tech1",
            "email": "tech1@dummy.com",
            "first_name": "Muhammad Haziq",
            "last_name": "Rosli",
            "phone_number": "+60 12-345 6701",
            "job_title": "Network & Security Specialist",
            "department": "Network Engineering",
            "skills": [TicketCategory.NETWORK.value, TicketCategory.SERVER_INFRASTRUCTURE.value],
        },
        {
            "username": "tech2",
            "email": "tech2@dummy.com",
            "first_name": "Nurul Ain",
            "last_name": "Syafiqah",
            "phone_number": "+60 12-345 6702",
            "job_title": "IAM & Accounts Specialist",
            "department": "Identity & Access Management",
            "skills": [TicketCategory.ACCESS_ACCOUNTS.value, TicketCategory.SOFTWARE.value],
        },
        {
            "username": "tech3",
            "email": "tech3@dummy.com",
            "first_name": "Farhan Danial",
            "last_name": "Azman",
            "phone_number": "+60 12-345 6703",
            "job_title": "Hardware & Peripherals Tech",
            "department": "Endpoint Support",
            "skills": [TicketCategory.HARDWARE.value, TicketCategory.SOFTWARE.value],
        },
        {
            "username": "tech4",
            "email": "tech4@dummy.com",
            "first_name": "Siti Khadijah",
            "last_name": "Ahmad",
            "phone_number": "+60 12-345 6704",
            "job_title": "Messaging & Collaboration Tech",
            "department": "Corporate Communications IT",
            "skills": [TicketCategory.EMAIL_COMMUNICATION.value, TicketCategory.SOFTWARE.value],
        },
        {
            "username": "tech5",
            "email": "tech5@dummy.com",
            "first_name": "Daniel Tan",
            "last_name": "Wei Lun",
            "phone_number": "+60 12-345 6705",
            "job_title": "Cloud & Infrastructure Engineer",
            "department": "Cloud Systems & DevOps",
            "skills": [TicketCategory.SERVER_INFRASTRUCTURE.value, TicketCategory.NETWORK.value],
        },
        {
            "username": "tech6",
            "email": "tech6@dummy.com",
            "first_name": "Amirah Balqis",
            "last_name": "Yusof",
            "phone_number": "+60 12-345 6706",
            "job_title": "Senior Desktop Support Tech",
            "department": "Client Services",
            "skills": [TicketCategory.HARDWARE.value, TicketCategory.SOFTWARE.value, TicketCategory.ACCESS_ACCOUNTS.value],
        },
        {
            "username": "tech7",
            "email": "tech7@dummy.com",
            "first_name": "Haris Iskandar",
            "last_name": "Zulkifli",
            "phone_number": "+60 12-345 6707",
            "job_title": "Telecom & Wi-Fi Specialist",
            "department": "Network Engineering",
            "skills": [TicketCategory.NETWORK.value, TicketCategory.HARDWARE.value],
        },
        {
            "username": "tech8",
            "email": "tech8@dummy.com",
            "first_name": "Priyah",
            "last_name": "Muthusamy",
            "phone_number": "+60 12-345 6708",
            "job_title": "Software & Applications Analyst",
            "department": "Business Applications",
            "skills": [TicketCategory.SOFTWARE.value, TicketCategory.EMAIL_COMMUNICATION.value],
        },
        {
            "username": "tech9",
            "email": "tech9@dummy.com",
            "first_name": "Ahmad Zikri",
            "last_name": "Mansor",
            "phone_number": "+60 12-345 6709",
            "job_title": "Systems Administrator",
            "department": "Infrastructure & Operations",
            "skills": [TicketCategory.SERVER_INFRASTRUCTURE.value, TicketCategory.ACCESS_ACCOUNTS.value],
        },
        {
            "username": "tech10",
            "email": "tech10@dummy.com",
            "first_name": "Melissa Wong",
            "last_name": "Pei Shan",
            "phone_number": "+60 12-345 6710",
            "job_title": "Tier 2 IT Support Engineer",
            "department": "Technical Support Center",
            "skills": [
                TicketCategory.HARDWARE.value,
                TicketCategory.NETWORK.value,
                TicketCategory.SOFTWARE.value,
                TicketCategory.ACCESS_ACCOUNTS.value,
                TicketCategory.EMAIL_COMMUNICATION.value,
                TicketCategory.SERVER_INFRASTRUCTURE.value,
            ],
        },
    ]

    created_techs = {}
    for t_info in technicians_data:
        u = User.query.filter_by(username=t_info["username"]).first()
        if not u:
            u = User(
                organization_id=org.id,
                username=t_info["username"],
                email=t_info["email"],
                first_name=t_info["first_name"],
                last_name=t_info["last_name"],
                role=UserRole.TECHNICIAN,
                phone_number=t_info["phone_number"],
                job_title=t_info["job_title"],
                department=t_info["department"],
                company_name="Beyond2U Sdn Bhd",
                address="Beyond2U Sdn Berhad",
                is_active=True,
                is_available=True,
            )
            u.set_password("TechPassword123!")
            db.session.add(u)
            db.session.flush()
            print(f"  - Created Technician: {u.username} ({u.email})")
        else:
            u.email = t_info["email"]
            u.address = "Beyond2U Sdn Berhad"
            u.set_password("TechPassword123!")

        created_techs[t_info["username"]] = u

        # Assign skills
        for cat in t_info["skills"]:
            skill = skill_objs.get(cat)
            if skill:
                ts = TechnicianSkill.query.filter_by(technician_id=u.id, skill_id=skill.id).first()
                if not ts:
                    ts = TechnicianSkill(technician_id=u.id, skill_id=skill.id, proficiency=5)
                    db.session.add(ts)

    # 6. 10 Clients
    clients_data = [
        {
            "username": "client1",
            "email": "client1@dummy.com",
            "first_name": "Aina Farhana",
            "last_name": "Kamaruddin",
            "phone_number": "+60 17-888 1001",
            "job_title": "HR Operations Executive",
            "department": "Human Resources",
            "company_name": "RHB Bank Berhad",
            "address": "Tower 2, RHB Centre, Jalan Tun Razak, Kuala Lumpur",
        },
        {
            "username": "client2",
            "email": "client2@dummy.com",
            "first_name": "Mohd Syahmi",
            "last_name": "Razak",
            "phone_number": "+60 17-888 1002",
            "job_title": "Senior Financial Analyst",
            "department": "Finance & Accounts",
            "company_name": "AmBank Group",
            "address": "Menara AmBank, 8 Jalan Yap Kwan Seng, Kuala Lumpur",
        },
        {
            "username": "client3",
            "email": "client3@dummy.com",
            "first_name": "Nadia Sofia",
            "last_name": "Ramli",
            "phone_number": "+60 17-888 1003",
            "job_title": "Digital Marketing Lead",
            "department": "Marketing & Public Relations",
            "company_name": "Sunway Group",
            "address": "Menara Sunway, Bandar Sunway, Subang Jaya, Selangor",
        },
        {
            "username": "client4",
            "email": "client4@dummy.com",
            "first_name": "Chong Wei Kiat",
            "last_name": "Brendan",
            "phone_number": "+60 17-888 1004",
            "job_title": "Procurement Specialist",
            "department": "Supply Chain & Procurement",
            "company_name": "Maybank Berhad",
            "address": "Menara Maybank, 100 Jalan Tun Perak, Kuala Lumpur",
        },
        {
            "username": "client5",
            "email": "client5@dummy.com",
            "first_name": "Fazrul Hisham",
            "last_name": "Shukor",
            "phone_number": "+60 17-888 1005",
            "job_title": "Software Developer",
            "department": "Product Engineering",
            "company_name": "CIMB Group Holdings",
            "address": "Menara CIMB, Jalan Stesen Sentral 2, KL Sentral, Kuala Lumpur",
        },
        {
            "username": "client6",
            "email": "client6@dummy.com",
            "first_name": "Anis Nabilah",
            "last_name": "Othman",
            "phone_number": "+60 17-888 1006",
            "job_title": "Legal & Compliance Officer",
            "department": "Legal & Governance",
            "company_name": "Axiata Group Berhad",
            "address": "Axiata Tower, 9 Jalan Stesen Sentral 5, KL Sentral, Kuala Lumpur",
        },
        {
            "username": "client7",
            "email": "client7@dummy.com",
            "first_name": "Viknesh",
            "last_name": "Selvaraj",
            "phone_number": "+60 17-888 1007",
            "job_title": "Key Account Executive",
            "department": "Sales & Business Development",
            "company_name": "Maxis Berhad",
            "address": "Menara Maxis, Kuala Lumpur City Centre, Kuala Lumpur",
        },
        {
            "username": "client8",
            "email": "client8@dummy.com",
            "first_name": "Fatin Nur Athirah",
            "last_name": "Zahari",
            "phone_number": "+60 17-888 1008",
            "job_title": "Customer Success Manager",
            "department": "Customer Relations",
            "company_name": "Petronas Dagangan Berhad",
            "address": "Tower 1, PETRONAS Twin Towers, KLCC, Kuala Lumpur",
        },
        {
            "username": "client9",
            "email": "client9@dummy.com",
            "first_name": "Kavitha",
            "last_name": "Subramaniam",
            "phone_number": "+60 17-888 1009",
            "job_title": "Facilities & Office Manager",
            "department": "Administration & Facilities",
            "company_name": "Sime Darby Berhad",
            "address": "Menara Sime Darby, Oasis Square, Ara Damansara, Petaling Jaya",
        },
        {
            "username": "client10",
            "email": "client10@dummy.com",
            "first_name": "Zulhelmi",
            "last_name": "Shamsuddin",
            "phone_number": "+60 17-888 1010",
            "job_title": "Quality Assurance Analyst",
            "department": "Quality Assurance",
            "company_name": "Gamuda Berhad",
            "address": "Menara Gamuda, PJ Trade Centre, Damansara Perdana, Petaling Jaya",
        },
    ]

    created_clients = {}
    for c_info in clients_data:
        u = User.query.filter_by(username=c_info["username"]).first()
        if not u:
            u = User(
                organization_id=org.id,
                username=c_info["username"],
                email=c_info["email"],
                first_name=c_info["first_name"],
                last_name=c_info["last_name"],
                role=UserRole.CLIENT,
                phone_number=c_info["phone_number"],
                job_title=c_info["job_title"],
                department=c_info["department"],
                company_name=c_info["company_name"],
                address=c_info["address"],
                is_active=True,
                is_available=True,
            )
            u.set_password("ClientPassword123!")
            db.session.add(u)
            db.session.flush()
            print(f"  - Created Client: {u.username} ({u.email})")
        else:
            u.email = c_info["email"]
            u.company_name = c_info["company_name"]
            u.address = c_info["address"]
            u.set_password("ClientPassword123!")

        created_clients[c_info["username"]] = u

    # 7. Create 5 Realistic Tickets
    if Ticket.query.count() == 0:
        tickets_seed = [
            {
                "client_key": "client1",
                "tech_key": "tech1",
                "subject": "VPN Gateway connection failure with error 412 from home office",
                "description": "Unable to establish an IPsec tunnel through Cisco AnyConnect VPN client while working remotely from home. The MFA push notification is approved on my mobile phone authenticator, but the VPN client times out with Error 412: Unable to establish an IPsec tunnel. I have restarted my laptop and Wi-Fi router, but the issue persists. Need urgent connection for the month-end payroll submission.",
                "status": TicketStatus.IN_PROGRESS,
                "resolution": None,
            },
            {
                "client_key": "client2",
                "tech_key": "tech2",
                "subject": "Active Directory corporate account lockout after password expiration",
                "description": "My corporate Windows account was locked out this morning after multiple password attempts following the 90-day password expiration policy. I cannot sign into my office PC, internal SAP ERP, or corporate OneDrive. Please assist with unlocking my account and issuing a temporary reset PIN.",
                "status": TicketStatus.IN_PROGRESS,
                "resolution": None,
            },
            {
                "client_key": "client3",
                "tech_key": "tech3",
                "subject": "External dual monitors flickering and blank screen on Thunderbolt dock",
                "description": "Both external Dell 27-inch monitors connected to my laptop via the USB-C docking station keep flickering and intermittently going to sleep with 'No Signal' message. Keyboard and mouse connected to the dock still work, but video output drops out every few minutes during graphic design work.",
                "status": TicketStatus.IN_PROGRESS,
                "resolution": None,
            },
            {
                "client_key": "client4",
                "tech_key": "tech4",
                "subject": "Microsoft Outlook disconnected loop and repeated credential prompt",
                "description": "Microsoft Outlook desktop application prompts for corporate password every 5 minutes and shows disconnected at the bottom right. Emails are not synchronizing and incoming supplier purchase orders cannot be retrieved.",
                "status": TicketStatus.RESOLVED,
                "resolution": "Cleared corrupted Office 365 cached credentials from Windows Credential Manager under Generic Credentials. Re-authenticated using Modern Authentication MFA push and verified Exchange mailbox synchronization is operational.",
            },
            {
                "client_key": "client5",
                "tech_key": "tech5",
                "subject": "Permission denied (publickey) when connecting to staging server via SSH bastion",
                "description": "Attempting to connect to the internal staging Linux cluster via the bastion jump proxy results in Permission Denied (publickey). ED25519 key was generated according to the security guidelines and registered. Need terminal shell access to deploy the new microservices build before end of day.",
                "status": TicketStatus.IN_PROGRESS,
                "resolution": None,
            },
        ]

        for t_seed in tickets_seed:
            submitter = created_clients[t_seed["client_key"]]
            assigned_tech = created_techs[t_seed["tech_key"]]

            t = TicketService.create_ticket(
                submitter=submitter,
                subject=t_seed["subject"],
                description=t_seed["description"],
            )

            # Assign and transition status
            t.assignee_id = assigned_tech.id
            t.status = t_seed["status"]
            if t_seed["resolution"]:
                t.resolution_summary = t_seed["resolution"]

            print(f"  - Created Ticket: {t.ticket_number} [{t.category.value if t.category else 'General'}] -> Assigned to {assigned_tech.username}")

    db.session.commit()
    print("Database seeding completed successfully!")


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        run_seed(app)
