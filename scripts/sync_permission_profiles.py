"""
VaidyaMD HMS — Canonical Permission Profiles Seeder & Sync Script
"""

import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.core.models import PermissionProfile, User, Hospital

CANONICAL_DEFAULTS = {
    'admin': {
        'name': 'Administrator / Medical Director',
        'desc': 'Full clinical, administrative, lab, and financial permissions across all hospital branches',
        'perms': {
            'patients': True, 'patient_register': True, 'patient_360': True, 'appointments': True,
            'treatment_cycles': True, 'cosgyn': True, 'counseling': True, 'ivf_lab': True,
            'cryopreservation': True, 'lims': True, 'ipd': True, 'pharmacy': True,
            'billing': True, 'wallet': True, 'referrals': True, 'analytics': True, 'settings': True
        }
    },
    'doctor': {
        'name': 'Doctor / Consultant',
        'desc': 'Clinical consultations, prescriptions, ultrasound tracking, and couple EMR access',
        'perms': {
            'patients': True, 'patient_register': True, 'patient_360': True, 'appointments': True,
            'treatment_cycles': True, 'cosgyn': True, 'counseling': True, 'ivf_lab': True,
            'cryopreservation': True, 'lims': True, 'ipd': True, 'pharmacy': True,
            'billing': True, 'wallet': False, 'referrals': True, 'analytics': True, 'settings': False
        }
    },
    'nurse': {
        'name': 'Fertility Nurse / Coordinator',
        'desc': 'Patient intake, vitals, nursing notes, and medication calendar administration',
        'perms': {
            'patients': True, 'patient_register': True, 'patient_360': True, 'appointments': True,
            'treatment_cycles': True, 'cosgyn': True, 'counseling': True, 'ivf_lab': False,
            'cryopreservation': False, 'lims': False, 'ipd': True, 'pharmacy': True,
            'billing': False, 'wallet': False, 'referrals': False, 'analytics': False, 'settings': False
        }
    },
    'receptionist': {
        'name': 'Front Desk Receptionist',
        'desc': 'Patient registration, appointment scheduling, and front-desk visitor flow',
        'perms': {
            'patients': True, 'patient_register': True, 'patient_360': True, 'appointments': True,
            'treatment_cycles': False, 'cosgyn': True, 'counseling': False, 'ivf_lab': False,
            'cryopreservation': False, 'lims': False, 'ipd': True, 'pharmacy': False,
            'billing': True, 'wallet': False, 'referrals': True, 'analytics': False, 'settings': False
        }
    },
    'embryologist': {
        'name': 'Clinical Embryologist',
        'desc': 'IVF lab dish preparation, ICSI, culture scoring, dual-witnessing, and cryobank straw coordinates',
        'perms': {
            'patients': True, 'patient_register': False, 'patient_360': True, 'appointments': False,
            'treatment_cycles': True, 'cosgyn': False, 'counseling': False, 'ivf_lab': True,
            'cryopreservation': True, 'lims': True, 'ipd': False, 'pharmacy': False,
            'billing': False, 'wallet': False, 'referrals': False, 'analytics': True, 'settings': False
        }
    },
    'andrologist': {
        'name': 'Andrologist / Semen Lab',
        'desc': 'Semen analysis (WHO 6th), sperm processing, swim-up, and DFI testing',
        'perms': {
            'patients': True, 'patient_register': False, 'patient_360': True, 'appointments': False,
            'treatment_cycles': False, 'cosgyn': False, 'counseling': False, 'ivf_lab': True,
            'cryopreservation': True, 'lims': True, 'ipd': False, 'pharmacy': False,
            'billing': False, 'wallet': False, 'referrals': False, 'analytics': False, 'settings': False
        }
    },
    'pharma': {
        'name': 'Lead Pharmacist',
        'desc': 'Pharmacy inventory, batch dispensing, FEFO management, and vendor purchase orders',
        'perms': {
            'patients': True, 'patient_register': False, 'patient_360': False, 'appointments': False,
            'treatment_cycles': False, 'cosgyn': False, 'counseling': False, 'ivf_lab': False,
            'cryopreservation': False, 'lims': False, 'ipd': False, 'pharmacy': True,
            'billing': True, 'wallet': False, 'referrals': False, 'analytics': False, 'settings': False
        }
    },
    'manager': {
        'name': 'Clinic Operations Manager',
        'desc': 'Operational reporting, branch oversight, bed allocation, and staff scheduling',
        'perms': {
            'patients': True, 'patient_register': True, 'patient_360': True, 'appointments': True,
            'treatment_cycles': True, 'cosgyn': True, 'counseling': True, 'ivf_lab': False,
            'cryopreservation': False, 'lims': False, 'ipd': True, 'pharmacy': False,
            'billing': True, 'wallet': True, 'referrals': True, 'analytics': True, 'settings': False
        }
    },
    'accounts': {
        'name': 'Billing & Accounts Desk',
        'desc': 'Invoicing, package assignments, advance wallet management, and payment receipts',
        'perms': {
            'patients': True, 'patient_register': True, 'patient_360': True, 'appointments': True,
            'treatment_cycles': False, 'cosgyn': True, 'counseling': False, 'ivf_lab': False,
            'cryopreservation': False, 'lims': False, 'ipd': True, 'pharmacy': False,
            'billing': True, 'wallet': True, 'referrals': True, 'analytics': True, 'settings': False
        }
    },
    'scanning': {
        'name': 'Ultrasonologist / Sonography',
        'desc': 'Folliculometry, TVS Doppler scans, cavity scans, and imaging reporting',
        'perms': {
            'patients': True, 'patient_register': False, 'patient_360': True, 'appointments': True,
            'treatment_cycles': True, 'cosgyn': False, 'counseling': False, 'ivf_lab': False,
            'cryopreservation': False, 'lims': True, 'ipd': False, 'pharmacy': False,
            'billing': False, 'wallet': False, 'referrals': False, 'analytics': False, 'settings': False
        }
    },
    'counsellor': {
        'name': 'Clinical Fertility Counsellor',
        'desc': 'Pre-ART psychological counseling, couple consent walkthroughs, and emotional support notes',
        'perms': {
            'patients': True, 'patient_register': True, 'patient_360': True, 'appointments': True,
            'treatment_cycles': True, 'cosgyn': False, 'counseling': True, 'ivf_lab': False,
            'cryopreservation': False, 'lims': False, 'ipd': False, 'pharmacy': False,
            'billing': False, 'wallet': False, 'referrals': False, 'analytics': False, 'settings': False
        }
    }
}

async def sync():
    async with AsyncSessionLocal() as session:
        hospitals = (await session.execute(select(Hospital))).scalars().all()
        for hosp in hospitals:
            print(f"Syncing profiles for hospital: {hosp.name} ({hosp.id})")
            existing_profiles = (await session.execute(
                select(PermissionProfile).where(PermissionProfile.hospital_id == hosp.id)
            )).scalars().all()
            
            profile_map = {}
            for p in existing_profiles:
                p_name = p.name.lower()
                for role_id in CANONICAL_DEFAULTS.keys():
                    if role_id in p_name or (role_id == 'nurse' and 'coordinator' in p_name) or (role_id == 'doctor' and 'consultant' in p_name) or (role_id == 'accounts' and 'billing' in p_name) or (role_id == 'pharma' and 'pharmacist' in p_name):
                        profile_map[role_id] = p
                        break
            
            for role_id, def_data in CANONICAL_DEFAULTS.items():
                if role_id in profile_map:
                    prof = profile_map[role_id]
                    updated_perms = dict(prof.menu_permissions or {})
                    for k, v in def_data['perms'].items():
                        if k not in updated_perms:
                            updated_perms[k] = v
                    prof.menu_permissions = updated_perms
                    print(f"  Updated existing profile: {prof.name}")
                else:
                    new_prof = PermissionProfile(
                        hospital_id=hosp.id,
                        name=def_data['name'],
                        description=def_data['desc'],
                        menu_permissions=def_data['perms'],
                        is_active=True
                    )
                    session.add(new_prof)
                    profile_map[role_id] = new_prof
                    print(f"  Created new profile: {def_data['name']}")
            
            await session.flush()
            
            # Now link existing hospital users to their matching profile if None
            users = (await session.execute(
                select(User).where(User.tenant_id == hosp.id)
            )).scalars().all()
            for u in users:
                u_role = str(u.role.value if hasattr(u.role, 'value') else u.role).lower()
                if u.permission_profile_id is None and u_role in profile_map:
                    u.permission_profile_id = profile_map[u_role].id
                    print(f"  Linked user {u.email} ({u_role}) -> profile {profile_map[u_role].name}")
        
        await session.commit()
        print("Profile sync complete successfully!")

if __name__ == '__main__':
    asyncio.run(sync())
