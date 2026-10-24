#!/usr/bin/env python
"""
Generate VAPID keys without npm
Run: python generate_vapid.py
"""

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend
    import base64
except ImportError:
    print("Installing cryptography...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'cryptography'])
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend
    import base64

def generate_vapid():
    # Generate key pair
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()
    
    # Export keys
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Convert to URL-safe base64
    def encode_key(data):
        return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')
    
    private_b64 = encode_key(private_pem)
    public_b64 = encode_key(public_pem)
    
    print("\n" + "=" * 60)
    print("🔑 VAPID KEYS GENERATED")
    print("=" * 60)
    print("\n📌 PUBLIC KEY (Add to your PWA JavaScript):")
    print(public_b64)
    print("\n🔒 PRIVATE KEY (Keep this secret!):")
    print(private_b64)
    print("\n" + "=" * 60)
    
    # Save to file
    with open('vapid_keys.txt', 'w') as f:
        f.write("VAPID Keys - Keep this file secure!\n")
        f.write("=" * 50 + "\n")
        f.write(f"PUBLIC_KEY={public_b64}\n")
        f.write(f"PRIVATE_KEY={private_b64}\n")
        f.write("=" * 50 + "\n")
    
    print("✅ Keys saved to: vapid_keys.txt")
    print("\n📝 Add to settings.py:")
    print(f"""
PWA_SETTINGS = {{
    'VAPID_PUBLIC_KEY': '{public_b64}',
    'VAPID_PRIVATE_KEY': '{private_b64}',
    'VAPID_EMAIL': 'your-email@example.com',
}}
    """)
    print("\n📝 Add to pwa.js:")
    print(f"""
applicationServerKey: this.urlBase64ToUint8Array(
    '{public_b64}'
)
    """)
    print("=" * 60)

if __name__ == '__main__':
    generate_vapid()
