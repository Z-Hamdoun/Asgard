from OpenSSL import crypto
import os

def generate_self_signed_cert():
    # Create certs directory if it doesn't exist
    if not os.path.exists('certs'):
        os.makedirs('certs')

    # Generate key
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)

    # Generate certificate
    cert = crypto.X509()
    cert.get_subject().C = "FR"
    cert.get_subject().ST = "State"
    cert.get_subject().L = "City"
    cert.get_subject().O = "Organization"
    cert.get_subject().OU = "Organizational Unit"
    cert.get_subject().CN = "localhost"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(365*24*60*60)  # Valid for one year
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')

    # Write certificate
    with open("certs/cert.pem", "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    
    # Write private key
    with open("certs/key.pem", "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

if __name__ == '__main__':
    generate_self_signed_cert()
    print("SSL certificates generated successfully in the 'certs' directory") 