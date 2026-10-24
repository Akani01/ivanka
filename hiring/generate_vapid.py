import base64
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend

def generate_vapid_keys():
    """Generate VAPID keys for push notifications"""
    
    # Generate private key
    private_key = ec.generate_private_key(
        ec.SECDER256(),
        default_backend()
    )
    
    # Get public key
    public_key = private_key.public_key()
    
    # Serialize to PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Convert to base64 URL safe
    private_b64 = base64.urlsafe_b64encode(private_pem).decode('utf-8').rstrip('=')
    public_b64 = base64.urlsafe_b64encode(public_pem).decode('utf-8').rstrip('=')
    
    print("=" * 50)
    print("VAPID KEYS GENERATED")
    print("=" * 50)
    print("\n🔑 PUBLIC KEY (use this in your frontend):")
    print(public_b64)
    print("\n🔒 PRIVATE KEY (keep this secret!):")
    print(private_b64)
    print("\n" + "=" * 50)
    print("Add these to your settings.py:")
    print(f"""
PWA_SETTINGS = {{
    'VAPID_PUBLIC_KEY': '{public_b64}',
    'VAPID_PRIVATE_KEY': '{private_b64}',
    'VAPID_EMAIL': 'your-email@example.com',
}}
    """)
    print("=" * 50)
    
    # Save to file
    with open('vapid_keys.txt', 'w') as f:
        f.write(f"Public Key: {public_b64}\n")
        f.write(f"Private Key: {private_b64}\n")
    
    print("✅ Keys saved to vapid_keys.txt")
    
    return public_b64, private_b64

if __name__ == '__main__':
    # Install cryptography if not installed
    try:
        import cryptography
    except ImportError:
        print("📦 Installing cryptography...")
        os.system('pip install cryptography')
        import cryptography
    
    generate_vapid_keys()