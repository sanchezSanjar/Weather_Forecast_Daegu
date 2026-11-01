// WeatherDaegu.exe: starts the Weather Forecast Daegu dashboard (Streamlit) hidden and opens it in the browser.
// Build: launcher\build.bat
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("Weather Forecast Daegu")]
[assembly: System.Reflection.AssemblyProduct("Weather Forecast Daegu")]
[assembly: System.Reflection.AssemblyVersion("1.0.0.0")]

static class WeatherDaeguLauncher
{
    // Windows (Hyper-V/WSL) reserves changing port ranges, so ask the OS for a free port each start
    // and remember it in weather.port to find a dashboard that is already running.
    static int Port;
    static string Url { get { return "http://localhost:" + Port; } }

    [STAThread]
    static int Main()
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(dir, @".venv\Scripts\python.exe");
        string log = Path.Combine(dir, "weather.log");
        string portFile = Path.Combine(dir, "weather.port");

        int saved;
        if (File.Exists(portFile) && int.TryParse(File.ReadAllText(portFile).Trim(), out saved))
        {
            Port = saved;
            if (IsRunning())
            {
                OpenBrowser();
                return 0;
            }
        }
        if (!File.Exists(Path.Combine(dir, "app.py")))
            return Warn("app.py was not found. Keep WeatherDaegu.exe inside the project folder " +
                        "(use a shortcut to start it from the Desktop).");
        if (!File.Exists(python) || !File.Exists(Path.Combine(dir, @"data\daegu_daily.csv")))
            return Warn("Weather Forecast Daegu is not set up yet.\n\nDouble-click INSTALL_WINDOWS.bat " +
                        "(needs internet once), then open WeatherDaegu.exe again.");

        Port = FreePort();
        File.WriteAllText(portFile, Port.ToString());
        string command = "/c \"\"" + python + "\" -m streamlit run app.py --server.headless true " +
                         "--server.address localhost --server.port " + Port + " > weather.log 2>&1\"";
        Process server;
        try
        {
            server = Process.Start(new ProcessStartInfo("cmd.exe", command)
            {
                WorkingDirectory = dir,
                UseShellExecute = false,
                CreateNoWindow = true,
            });
        }
        catch (Exception ex)
        {
            return Warn("Could not start Python: " + ex.Message);
        }

        Application.EnableVisualStyles();
        var splash = new Form
        {
            Text = "Weather Forecast Daegu",
            Size = new Size(380, 140),
            FormBorderStyle = FormBorderStyle.FixedDialog,
            StartPosition = FormStartPosition.CenterScreen,
            MaximizeBox = false,
            MinimizeBox = false,
            BackColor = Color.White,
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath),
        };
        splash.Controls.Add(new Label
        {
            Text = "Starting Weather Forecast Daegu...\nThe dashboard opens in your browser.",
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleCenter,
            Font = new Font("Segoe UI", 10),
            ForeColor = Color.FromArgb(29, 78, 137),
        });

        int result = 0;
        var started = DateTime.Now;
        var timer = new Timer { Interval = 500 };
        timer.Tick += (s, e) =>
        {
            if (IsRunning())
            {
                timer.Stop();
                OpenBrowser();
                splash.Close();
            }
            else if (server.HasExited || (DateTime.Now - started).TotalSeconds > 120)
            {
                timer.Stop();
                splash.Hide();
                result = Warn("Weather Forecast Daegu could not start.\n\n" + Tail(log) + "\n\nLog: " + log);
                splash.Close();
            }
        };
        splash.Shown += (s, e) => timer.Start();
        Application.Run(splash);
        return result;
    }

    static int FreePort()
    {
        var listener = new System.Net.Sockets.TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        int port = ((IPEndPoint)listener.LocalEndpoint).Port;
        listener.Stop();
        return port;
    }

    static bool IsRunning()
    {
        try
        {
            // 127.0.0.1 avoids a slow IPv6 attempt for "localhost".
            var request = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + Port + "/_stcore/health");
            request.Timeout = 400;
            using (var response = (HttpWebResponse)request.GetResponse())
                return response.StatusCode == HttpStatusCode.OK;
        }
        catch (WebException)
        {
            return false;
        }
    }

    static void OpenBrowser()
    {
        Process.Start(new ProcessStartInfo(Url) { UseShellExecute = true });
    }

    static string Tail(string path)
    {
        if (!File.Exists(path))
            return "(no log)";
        using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
        using (var reader = new StreamReader(stream))
        {
            var lines = reader.ReadToEnd().Split('\n');
            return string.Join("\n", lines.Skip(Math.Max(0, lines.Length - 10)));
        }
    }

    static int Warn(string message)
    {
        MessageBox.Show(message, "Weather Forecast Daegu", MessageBoxButtons.OK, MessageBoxIcon.Information);
        return 1;
    }
}
