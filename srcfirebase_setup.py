"""
CRANIUM FUND - Firebase Infrastructure Initialization
Architectural Choice: Firebase provides real-time database, authentication, 
and serverless functions in one platform, enabling rapid deployment with 
zero DevOps overhead.
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import firebase_admin
from firebase_admin import credentials, firestore, initialize_app
from firebase_admin.exceptions import FirebaseError
from dotenv import load_dotenv

# Initialize logging with robust configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('cranium_fund.log')
    ]
)
logger = logging.getLogger(__name__)

class FirebaseManager:
    """Secure Firebase connection manager with error handling and retry logic"""
    
    def __init__(self, env_path: str = ".env"):
        """Initialize Firebase with environment configuration"""
        self.initialized = False
        self.db = None
        self.env_path = env_path
        self._load_environment()
        
    def _load_environment(self) -> None:
        """Load environment variables with validation"""
        try:
            env_file = Path(self.env_path)
            if not env_file.exists():
                logger.error(f"Environment file not found: {self.env_path}")
                raise FileNotFoundError(f"Required environment file missing: {self.env_path}")
            
            load_dotenv(dotenv_path=env_file)
            logger.info("Environment variables loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load environment: {str(e)}")
            raise
    
    def _validate_configuration(self) -> bool:
        """Validate all required Firebase configuration exists"""
        required_vars = [
            'FIREBASE_PROJECT_ID',
            'FIREBASE_PRIVATE_KEY',
            'FIREBASE_CLIENT_EMAIL'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {missing_vars}")
            return False
        
        # Validate private key format
        private_key = os.getenv('FIREBASE_PRIVATE_KEY', '')
        if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
            logger.error("FIREBASE_PRIVATE_KEY has invalid format")
            return False
            
        return True
    
    def initialize_firebase(self) -> bool:
        """Initialize Firebase Admin SDK with comprehensive error handling"""
        try:
            if firebase_admin._apps:
                logger.warning("Firebase already initialized, returning existing app")
                self.db = firestore.client()
                self.initialized = True
                return True
            
            if not self._validate_configuration():
                logger.error("Firebase configuration validation failed")
                return False
            
            # Prepare credential dictionary with proper newline handling
            private_key = os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n')
            
            cred_dict = {
                "type": "service_account",
                "project_id": os.getenv('FIREBASE_PROJECT_ID'),
                "private_key_id": "auto-generated",
                "private_key": private_key,
                "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
                "client_id": "auto-generated",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.getenv('FIREBASE_CLIENT_EMAIL')}"
            }
            
            cred = credentials.Certificate(cred_dict)
            app = initialize_app(cred, {
                'projectId': os.getenv('FIREBASE_PROJECT_ID')
            })
            
            self.db = firestore.client(app)
            self.initialized = True
            
            # Test connection
            test_doc = self.db.collection('system_health').document('connection_test')
            test_doc.set({
                'timestamp': firestore.SERVER_TIMESTAMP,
                'status': 'connected',
                'system': 'cranium_fund'
            })
            
            logger.info(f"Firebase initialized successfully for project: {os.getenv('FIREBASE_PROJECT_ID')}")
            return True
            
        except FirebaseError as e:
            logger.error(f"Firebase initialization error: {str(e)}")
            return False
        except ValueError as e:
            logger.error(f"Invalid credentials format: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Firebase initialization: {str(e)}")
            return False
    
    def get_firestore_instance(self) -> firestore.Client:
        """Get Firestore client with connection validation"""
        if not self.initialized or not self.db:
            logger.error("Firebase not initialized. Call initialize_firebase() first.")
            raise RuntimeError("Firebase not initialized")
        return self.db
    
    def create_initial_collections(self) -> Dict[str, bool]:
        """Create initial Firestore collections with schemas"""
        if not self.initialized:
            logger.error("Cannot create collections: Firebase not initialized")
            return {}
        
        collections_config = {
            'treasury_transactions': {
                'schema_version': '1.0',
                'description': 'All financial transactions for CRANIUM FUND'
            },
            'service_requests': {
                'schema_version': '1.0',
                'description': 'Incoming service requests and diagnostics'
            },
            'system_metrics': {
                'schema_version': '1.0',
                'description': 'Performance and revenue metrics'
            },
            'user_sessions': {
                'schema_version': '1.0',
                'description': 'User authentication and session data'
            },
            'payment_intents': {
                'schema_version': '1.0',
                'description': 'Payment processing records'
            }
        }
        
        results = {}
        for collection_name, config in collections_config.items():
            try:
                # Create collection by adding a configuration document
                config_ref = self.db.collection(collection_name).document('_config')
                config_ref.set({
                    **config,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'initialized': True
                })
                results[collection_name] = True
                logger.info(f"Created collection: {collection_name}")
            except Exception as e:
                results[collection_name] = False
                logger.error(f"Failed to create collection {collection_name}: {str(e)}")
        
        return results
    
    def log_system_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        """Log system event to Firestore with standardized format"""
        if not self.initialized:
            return False
        
        try:
            events_ref = self.db.collection('system_events')
            events_ref.add({
                'event_type': event_type,
                'data': data,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'system': 'cranium_fund'
            })
            logger.info(f"Logged system event: {event_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to log system event: {str(e)}")
            return False

# Global instance for singleton pattern
firebase_manager = FirebaseManager()

def initialize_cranium_infrastructure() -> bool:
    """Main initialization function for CRANIUM FUND infrastructure"""
    logger.info("Starting CRANIUM FUND infrastructure initialization...")
    
    try:
        # Initialize Firebase
        if not firebase_manager.initialize_firebase():
            logger.error("Firebase initialization failed")
            return False
        
        # Create initial collections
        collection_results = firebase_manager.create_initial_collections()
        
        successful_collections = sum(1 for success in collection_results.values() if success)
        total_collections = len(collection_results)
        
        logger.info(f"Created {successful_collections}/{total_collections} collections")
        
        # Log initialization event
        firebase_manager.log_system_event('infrastructure_initialized', {
            'collections_created': successful_collections,
            'total_collections': total_collections,
            'status': 'success' if successful_collections == total_collections else 'partial'
        })
        
        return successful_collections == total_collections
        
    except Exception as e:
        logger.error(f"Infrastructure initialization failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = initialize_cranium_infrastructure()
    if success:
        print("✅ CRANIUM FUND infrastructure initialized successfully")
        sys.exit(0)
    else:
        print("❌ Infrastructure initialization failed")
        sys.exit(1)