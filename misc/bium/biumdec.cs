/*
Decrypts beatmania IIDX ULTIMATE MOBILE files (by bnnm)

compile: C:\Windows\Microsoft.NET\Framework\(version)\csc.exe /t:exe /out:biumdec.exe biumdec.cs
(needs +v4.0)

Files are encrypted using a manual implementation of AES-CTR using the filename get the base key + AES-ECB to encrypt the counter.
This mostly adapts original C# code since it uses some arcane MS stuff like PasswordDeriveBytes.
Original decryptor is for a Filestream but this is simplified.

(I don't really know any C# so expect code to be wonky).

Reversing:
- get il2cpp.so + global-metada.dat from .apk/ipa
- get Il2CppDumper and run with the above 2 files, will generate some files
- load il2cpp.so into IDA/Ghidra, wait a while
- open script "ida_with_struct_py3.py" or "ghidra_with_struct.py", select script.json + il2cpp.h, wait a while
- poke around

Main interesting stuff:
- AssetManager.AssetBundles.AssetBundleCryptoStream: .ctor = inits AES; .Read/cipher = main decryption
- AssetManager.AssetBundles.AssetBundleList: .Load = decrypt/loads ablist.json
- others like AssetBundlePathManager or AssetLoader may contain how urls are generated
*/

using System;
using System.IO;
using System.Text;
using System.Security.Cryptography;

public class Decryptor : IDisposable {
	private static int BLOCK_SIZE = 0x10; //AES block

	private PasswordDeriveBytes pdb;
	private AesManaged aes;
	private ICryptoTransform encryptor;
	private byte[] blkBuffer = new byte[BLOCK_SIZE];
	private byte[] xorBuffer = new byte[BLOCK_SIZE];
	private UInt64 offset;
	private UInt64 blockNumber;
	private FileStream src;
	private FileStream dst;

    public Decryptor(String filename, String name) {
        // only useful for ablist.json
		if (name == null) {
			name = Path.GetFileName(filename);
		}

		String password = name;
		//String password = Encoding.UTF8.GetBytes(name); //equivalent
		byte[] salt = MakeSalt(name);

		// base AES-ECB and key used to create CTR xor pads
		pdb = new PasswordDeriveBytes(password, salt);

		aes = new AesManaged();
		aes.KeySize = 128; 
		aes.Mode = CipherMode.ECB; 
		aes.Padding = PaddingMode.None; 
		//aes.IV = (unused);
		aes.Key = pdb.GetBytes(aes.KeySize / 8); //each GetBytes returns a new key

		encryptor = aes.CreateEncryptor(aes.Key, aes.IV);
		
		src = new FileStream(filename, FileMode.Open);
		dst = new FileStream(filename + ".dec", FileMode.Create);
		Reset();
	}
	
	private void Reset() {
		offset = 0;
		blockNumber = (offset / (UInt64)BLOCK_SIZE) + 1;
	}

	// plain UTF8 filename, but paded to >= 8 if needed (can be bigger, and exact size matters for PasswordDeriveBytes)
	private byte[] MakeSalt(String name) {
		while (name.Length < 8) {
			name += name;
		}

		return Encoding.UTF8.GetBytes(name);
	}

    public void Process() {
		byte[] input = new byte[BLOCK_SIZE];
		Reset();

		//TODO maybe read using bigger chunks to reduce calls
		while (true) {
			int bytes = src.Read(input, 0, input.Length);	
			if (bytes <= 0)
				break;
			ProcessBlock(input, bytes);
			dst.Write(input, 0, bytes);
		}
    }

	// decrypt current block N (starts from 1)
    public void ProcessBlock(byte[] buf, int bytes) {
		int inputCount = blkBuffer.Length;
	 	//current num to LE array (example: int block 0x1122 = {0x22, 0x11, 0x00, 0x00}) then copy to full-sized array
		byte[] tmpBuffer = System.BitConverter.GetBytes(blockNumber);
		tmpBuffer.CopyTo(blkBuffer, 0);

		// encrypt current block number with filename-key + AES-ECB to get CTR xor.
		encryptor.TransformBlock(blkBuffer, 0, inputCount, xorBuffer, 0);
		blockNumber += 1;

		for (int i = 0; i < bytes; i++) {
			buf[i] ^= xorBuffer[i];
		}
	}

    public void Dispose() {
        if (pdb != null) pdb.Dispose();
		if (encryptor != null) encryptor.Dispose();
        if (aes != null) aes.Dispose();
		if (src != null) src.Dispose();
		if (dst != null) dst.Dispose();
    }

    public static void Main(String[] args) {
		String filename = null;
		String name = null;
		
		if (args == null || args.Length < 2) {
			Console.WriteLine("beatmania IIDX ULTIMATE MOBILE decryptor by bnnm");
			Console.WriteLine("Usage: biumdec.exe filename bundleName");
            Console.WriteLine("");
            Console.WriteLine("* Needs bundleName as found inside ablist.json (for hashed filenames)");
            Console.WriteLine("* bundleName for ablist.json is ablist.json");
			return;
		}

		if (args != null && args.Length > 0)
			filename = args[0];
		if (args != null && args.Length > 1)
			name = args[1];

		
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
