using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

public static class Tlg5ToPng
{
    private static int DecodeLzss(byte[] src, int srcOffset, int srcLen, byte[] dst, int dstOffset, int outLen, byte[] text, ref int r)
    {
        int flags = 0;
        int si = srcOffset;
        int sEnd = srcOffset + srcLen;
        int di = dstOffset;
        int dEnd = dstOffset + outLen;
        while (di < dEnd && si < sEnd)
        {
            flags >>= 1;
            if ((flags & 0x100) == 0)
            {
                if (si >= sEnd) break;
                flags = src[si++] | 0xFF00;
            }
            if ((flags & 1) != 0)
            {
                if (si + 1 >= sEnd) break;
                int x0 = src[si++];
                int x1 = src[si++];
                int pos = x0 | ((x1 & 0x0F) << 8);
                int len = ((x1 & 0xF0) >> 4) + 3;
                if (len == 18)
                {
                    if (si >= sEnd) break;
                    len += src[si++];
                }
                for (int k = 0; k < len && di < dEnd; k++)
                {
                    byte b = text[pos];
                    pos = (pos + 1) & 0xFFF;
                    text[r] = b;
                    r = (r + 1) & 0xFFF;
                    dst[di++] = b;
                }
            }
            else
            {
                if (si >= sEnd) break;
                byte b = src[si++];
                text[r] = b;
                r = (r + 1) & 0xFFF;
                dst[di++] = b;
            }
        }
        return di - dstOffset;
    }

    public static void ConvertFile(string inPath, string outPath)
    {
        byte[] data = File.ReadAllBytes(inPath);
        if (data.Length < 11) throw new InvalidDataException("Too short: " + inPath);
        string sig = Encoding.ASCII.GetString(data, 0, 6);
        int pos = 0;
        if (sig == "TLG0.0")
        {
            // TLG0.0\0sds\x1a + 4-byte raw length
            pos = 15;
            sig = Encoding.ASCII.GetString(data, pos, 6);
        }
        if (sig != "TLG5.0") throw new InvalidDataException("Not TLG5.0: " + sig + " in " + inPath);
        int colors = data[pos + 11];
        if (colors != 3 && colors != 4) throw new InvalidDataException("Unsupported TLG5 colors=" + colors);
        int width = BitConverter.ToInt32(data, pos + 12);
        int height = BitConverter.ToInt32(data, pos + 16);
        int blockHeight = BitConverter.ToInt32(data, pos + 20);
        int blockCount = (height - 1) / blockHeight + 1;
        int cur = pos + 24 + blockCount * 4;

        byte[] text = new byte[4096];
        int r = 0;
        byte[][] outbuf = new byte[4][];
        for (int c = 0; c < colors; c++) outbuf[c] = new byte[blockHeight * width];
        byte[] prevLine = new byte[width * 4];
        byte[] argb = new byte[width * height * 4];

        for (int yBlk = 0; yBlk < height; yBlk += blockHeight)
        {
            int lines = Math.Min(blockHeight, height - yBlk);
            for (int c = 0; c < colors; c++)
            {
                int mark = data[cur++];
                int size = BitConverter.ToInt32(data, cur);
                cur += 4;
                if (mark == 0)
                {
                    DecodeLzss(data, cur, size, outbuf[c], 0, lines * width, text, ref r);
                }
                else
                {
                    Buffer.BlockCopy(data, cur, outbuf[c], 0, size);
                }
                cur += size;
            }
            for (int y = 0; y < lines; y++)
            {
                int rowOff = y * width;
                int prevB = 0, prevG = 0, prevR = 0, prevA = 0;
                int dstOff = (yBlk + y) * width * 4;
                for (int x = 0; x < width; x++)
                {
                    int b = outbuf[0][rowOff + x];
                    int g = outbuf[1][rowOff + x];
                    int rr = outbuf[2][rowOff + x];
                    int a = (colors == 4) ? outbuf[3][rowOff + x] : 0;
                    // Undo green-based correlation + horizontal delta
                    b = (b + g) & 0xFF;
                    rr = (rr + g) & 0xFF;
                    prevB = (prevB + b) & 0xFF;
                    prevG = (prevG + g) & 0xFF;
                    prevR = (prevR + rr) & 0xFF;
                    prevA = (prevA + a) & 0xFF;

                    int pIdx = x * 4;
                    byte pb = (byte)((prevLine[pIdx + 0] + prevB) & 0xFF);
                    byte pg = (byte)((prevLine[pIdx + 1] + prevG) & 0xFF);
                    byte pr = (byte)((prevLine[pIdx + 2] + prevR) & 0xFF);
                    byte pa = (colors == 4) ? (byte)((prevLine[pIdx + 3] + prevA) & 0xFF) : (byte)255;

                    prevLine[pIdx + 0] = pb;
                    prevLine[pIdx + 1] = pg;
                    prevLine[pIdx + 2] = pr;
                    prevLine[pIdx + 3] = pa;

                    argb[dstOff + pIdx + 0] = pb;
                    argb[dstOff + pIdx + 1] = pg;
                    argb[dstOff + pIdx + 2] = pr;
                    argb[dstOff + pIdx + 3] = pa;
                }
            }
        }

        Directory.CreateDirectory(Path.GetDirectoryName(outPath));
        using (var bmp = new Bitmap(width, height, PixelFormat.Format32bppArgb))
        {
            var rect = new Rectangle(0, 0, width, height);
            var bd = bmp.LockBits(rect, ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            try
            {
                if (bd.Stride == width * 4)
                    Marshal.Copy(argb, 0, bd.Scan0, argb.Length);
                else
                {
                    for (int y = 0; y < height; y++)
                        Marshal.Copy(argb, y * width * 4, IntPtr.Add(bd.Scan0, y * bd.Stride), width * 4);
                }
            }
            finally { bmp.UnlockBits(bd); }
            bmp.Save(outPath, ImageFormat.Png);
        }
    }

    public static int Main(string[] args)
    {
        if (args.Length < 2)
        {
            Console.Error.WriteLine("Usage: Tlg5ToPng <rawRoot> <outRoot>");
            return 1;
        }
        string rawRoot = Path.GetFullPath(args[0]);
        string outRoot = Path.GetFullPath(args[1]);
        var files = Directory.GetFiles(rawRoot, "*.tlg", SearchOption.AllDirectories);
        int converted = 0, skipped = 0;
        foreach (string f in files)
        {
            string rel = f.Substring(rawRoot.Length).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string outPath = Path.ChangeExtension(Path.Combine(outRoot, rel), ".png");
            if (File.Exists(outPath) && new FileInfo(outPath).Length > 0) { skipped++; continue; }
            ConvertFile(f, outPath);
            converted++;
        }
        Console.WriteLine("{\"converted\":" + converted + ",\"skipped\":" + skipped + ",\"total\":" + files.Length + "}");
        return 0;
    }
}
