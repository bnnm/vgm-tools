/*
Decrypts Shiren 6 Switch files (by bnnm)

compile: C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe /t:exe /out:shiren6dec.exe shiren6dec.cs
(needs +v4.0)

Files are encrypted using a manual implementation of AES-CTR using a fixed password + filename get salt.
This mostly adapts original C# code since it uses some arcane MS stuff like PasswordDeriveBytes.
Original decryptor is for a Filestream but this is simplified. There is probably some CTR mode from MS but who knows.

(I don't really know any C# so expect code to be wonky).
*/

using System;
using System.IO;
using System.Text;
using System.Security.Cryptography;

public class Decryptor : IDisposable {
	private static int BLOCK_SIZE = 0x10; //AES block

    private PasswordDeriveBytes pdb;
    private AesManaged aes;
    private ICryptoTransform cryptor;
    private FileStream src;
    private FileStream dst;
    //private CryptoStream dec;
	private byte[] blkBuffer = new byte[BLOCK_SIZE];
	private byte[] xorBuffer = new byte[BLOCK_SIZE];
	private UInt64 offset;
	private UInt64 blockNumber;

    public Decryptor(String filename, String name) {
        if (name == null) {
            name = Path.GetFileName(filename);
            name = Path.ChangeExtension(filename, null);
        }

        byte[] password = Encoding.UTF8.GetBytes("DtUp!43AZH46@*fj768GCM@ajNvEdBEB");
        byte[] salt = MakeSalt(name);

        // base AES-ECB and key used to create CTR xor pads
        pdb = new PasswordDeriveBytes(password, salt);

        aes = new AesManaged();
        aes.KeySize = 128; 
        aes.Mode = CipherMode.ECB; 
        aes.Padding = PaddingMode.None; 
        //aes.IV = (unused);
        aes.Key = pdb.GetBytes(aes.KeySize / 8); //each GetBytes returns a new key

        //cryptor = aes.CreateDecryptor(); //aes.Key, aes.IV
        cryptor = aes.CreateEncryptor(); //aes.Key, aes.IV
        
        src = new FileStream(filename, FileMode.Open);
        dst = new FileStream(filename + ".dec", FileMode.Create);
        //dec = new CryptoStream(src, decryptor, CryptoStreamMode.Read);
    }

    private byte[] MakeSalt(String name) {
        //while (name.Length < 8) {
        //    name += name;
        //}

        return Encoding.UTF8.GetBytes(name);
    }

	private void Reset() {
		offset = 0;
		blockNumber = (offset / (UInt64)BLOCK_SIZE) + 1;
	}

    public void Process() {
		byte[] input = new byte[BLOCK_SIZE];
		Reset();

        while (true) {
			int bytes = src.Read(input, 0, input.Length);	
			if (bytes <= 0)
				break;
			ProcessBlock(input, bytes);
			dst.Write(input, 0, bytes);

            /*
            int bytes = dec.Read(input, 0, input.Length);    
            if (bytes <= 0)
                break;
            dst.Write(input, 0, bytes);
            */
        }
    }
    
    // decrypt current block N (starts from 1)
    public void ProcessBlock(byte[] buf, int bytes) {
		int inputCount = blkBuffer.Length;
	 	//current num to LE array (example: int block 0x1122 = {0x22, 0x11, 0x00, 0x00}) then copy to full-sized array
		byte[] tmpBuffer = System.BitConverter.GetBytes(blockNumber);
		tmpBuffer.CopyTo(blkBuffer, 0);

		// encrypt current block number with filename-key + AES-ECB to get CTR xor.
		cryptor.TransformBlock(blkBuffer, 0, inputCount, xorBuffer, 0);
		blockNumber += 1;

		for (int i = 0; i < bytes; i++) {
			buf[i] ^= xorBuffer[i];
		}
	}

    public void Dispose() {
        if (pdb != null) pdb.Dispose();
        if (cryptor != null) cryptor.Dispose();
        if (aes != null) aes.Dispose();
        if (src != null) src.Dispose();
        if (dst != null) dst.Dispose();
        //if (dec != null) dec.Dispose();
    }

    public static void Main(String[] args) {
        String filename = null;
        String name = null;
        
        if (args == null || args.Length < 1) {
            Console.WriteLine("Shiren 6 decryptor by bnnm");
            Console.WriteLine("Usage: shiren6dec.exe filename");
            return;
        }

        if (args != null && args.Length > 0)
            filename = args[0];
        
        Decryptor dec = null;
        try {
            dec = new Decryptor(filename, name);

            Console.WriteLine("processing...");
            dec.Process();
            Console.WriteLine("done");
        } catch(System.IO.FileNotFoundException) {
            Console.WriteLine("File not found: " + filename);
        } finally {
            if (dec != null) dec.Dispose();
        }
        
    }
}
