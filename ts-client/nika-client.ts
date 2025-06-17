import WebSocket from 'ws';
import * as readline from 'readline';

class NikaClient {
    private ws: WebSocket;
    private rl: readline.Interface;

    constructor(url: string = 'ws://localhost:8090/ws_json') {
        this.ws = new WebSocket(url);
        this.rl = readline.createInterface({
            input: process.stdin,
            output: process.stdout
        });

        this.setupWebSocket();
        this.setupReadline();
    }

    private setupWebSocket() {
        this.ws.on('open', () => {
            console.log('Connected to Nika server');
        });

        this.ws.on('message', (data: WebSocket.Data) => {
            console.log('Received from server:', data.toString());
        });

        this.ws.on('error', (error) => {
            console.error('WebSocket error:', error);
        });

        this.ws.on('close', () => {
            console.log('Disconnected from server');
            process.exit(0);
        });
    }

    private setupReadline() {
        this.rl.on('line', (input: string) => {
            if (input.toLowerCase() === 'exit') {
                this.ws.close();
                this.rl.close();
                return;
            }

            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(input);
            } else {
                console.log('Not connected to server');
            }
        });
    }
}

// Create and start the client
const client = new NikaClient(); 