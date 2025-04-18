"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const child_process_1 = require("child_process");
const os = __importStar(require("os"));
const sharp_1 = __importDefault(require("sharp"));
const uuid_1 = require("uuid");
const SETTING_PATH = "/home/creux/Documents/AI/VIFagent/resources/plane/";
let storedDecorations = {}; // Object to store decoration types by a unique identifier
let storedRanges = {}; // Object to store ranges by the same identifier
const path = __importStar(require("path"));
function getEditorForDocument(doc) {
    return vscode.window.visibleTextEditors.find(editor => editor.document === doc);
}
async function drawBoxes(imagePath, boxescolors) {
    let tmpImagePathName = path.join(os.tmpdir(), (0, uuid_1.v4)() + ".png");
    const tmpImagePath = await copyToTemp(imagePath, tmpImagePathName);
    const svgs = [];
    const image = (0, sharp_1.default)(imagePath);
    const medatada = await image.metadata();
    boxescolors.forEach(boxcolor => {
        const box = boxcolor[0];
        const color = boxcolor[1];
        const [x, y, x2, y2] = box;
        const width = x2 - x;
        const height = y2 - y;
        const rgbString = `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
        const svg = `
      <svg version="1.1" width="${medatada.width}" height="${medatada.height}" xmlns="http://www.w3.org/2000/svg">
			<rect x="${x}" y="${y}" width="${width}" height="${height}"
			fill="none" stroke="${rgbString}" stroke-opacity="0.4" stroke-width="2"/>
      </svg>
			`;
        svgs.push({ input: Buffer.from(svg), top: 0, left: 0 });
    });
    await (0, sharp_1.default)(tmpImagePath.fsPath)
        .composite(svgs)
        .toFile(imagePath);
}
async function copyToTemp(sourcePath, existingFilePath) {
    const sourceUri = vscode.Uri.file(sourcePath);
    const targetUri = vscode.Uri.file(existingFilePath);
    await vscode.workspace.fs.copy(sourceUri, targetUri, { overwrite: true });
    return targetUri;
}
function activate(context) {
    console.log("Extension activated"); // Add this
    let disposable = vscode.commands.registerCommand('tikz-mapped.run-mapped', async () => {
        //creating the dummy editing file from the existing one (hardcoded path)
        const filePath = path.join(SETTING_PATH, 'code.tex');
        const imageFilePath = await copyToTemp(path.join(SETTING_PATH, 'image.png'), path.join(os.tmpdir(), "image.png"));
        //Opening the image and the code side to side
        const doc = await vscode.workspace.openTextDocument(filePath);
        await vscode.window.showTextDocument(doc, vscode.ViewColumn.One);
        await vscode.commands.executeCommand('vscode.open', vscode.Uri.file(imageFilePath.fsPath), vscode.ViewColumn.Two);
        if (doc == undefined) {
            vscode.window.showErrorMessage(`Error: file not found`);
            return;
        }
        const editor = getEditorForDocument(doc);
        if (editor == undefined) {
            vscode.window.showErrorMessage(`Error: editor undefined`);
            return;
        }
        //reset code decorations
        clearAllDecorations(editor);
        const input = await vscode.window.showInputBox({
            prompt: 'Enter a feature',
            placeHolder: 'ears, nose, mouth',
        });
        if (input === undefined) {
            vscode.window.showWarningMessage('User canceled input.');
            return;
        }
        //hardcoded scrip and resources
        const script_path = context.asAbsolutePath('get_mapping.sh');
        const pickle_path = path.join(SETTING_PATH, "p.pickle");
        (0, child_process_1.execFile)(script_path, [pickle_path, `"${input}"`], async (error, stdout, stderr) => {
            if (error) {
                vscode.window.showErrorMessage(`Error: ${error.message}`);
                return;
            }
            if (stderr) {
                vscode.window.showWarningMessage(`Stderr: ${stderr}`);
            }
            vscode.window.showInformationMessage(`Output: ${stdout}`);
            const parsed = JSON.parse(stdout);
            const mappings = parsed.map(([mapping, [score]]) => {
                return [
                    {
                        spans: mapping.spans,
                        zone: mapping.zone,
                    },
                    score,
                ];
            });
            const mappings_max = Math.max(...mappings.map(mappingwscore => {
                return mappingwscore[1];
            }));
            //coloring the code and adding the rectangles on the image
            const boxescolors = [];
            const uniquespans_rangescolors = new Map();
            //reversedso that the highest probable boxes are written over the other ones
            mappings.reverse().forEach(async (mapping, index) => {
                const adjusted_mapping = (((mapping[1] / mappings_max) ** 0.3) * 2) - 1;
                let red = 0;
                let blue = 0;
                if (adjusted_mapping > 0) {
                    blue = (150 + 105 * adjusted_mapping);
                }
                else {
                    red = (150 + 105 * (-adjusted_mapping));
                }
                const key = mapping[0].spans.map(span => String(span[0]) + String(span[1])).join("");
                uniquespans_rangescolors.set(key, [mapping[0].spans, [red, 0, blue]]);
                const zone = mapping[0].zone;
                boxescolors.push([zone, [red, 0, blue]]);
            });
            await drawBoxes(imageFilePath.fsPath, boxescolors);
            //adding decorations
            uniquespans_rangescolors.forEach((rangecolor, key) => {
                const ranges = rangecolor[0].map(s => new vscode.Range(doc.positionAt(s[0]), doc.positionAt(s[1])));
                const decorationType = vscode.window.createTextEditorDecorationType({
                    backgroundColor: 'rgba(' + rangecolor[1][0] + ', 0, ' + rangecolor[1][2] + ', 0.3)',
                });
                storedDecorations[`decoration${key}`] = decorationType;
                storedRanges[`decoration${key}`] = ranges;
                editor.setDecorations(decorationType, ranges);
            });
        });
    });
    context.subscriptions.push(disposable);
}
function deactivate() {
    for (const key in storedDecorations) {
        if (storedDecorations[key]) {
            storedDecorations[key].dispose();
        }
    }
}
function clearAllDecorations(editor) {
    for (const key in storedDecorations) {
        if (storedDecorations[key]) {
            editor.setDecorations(storedDecorations[key], []);
            storedDecorations[key].dispose();
        }
    }
    storedDecorations = {};
    storedRanges = {};
}
//# sourceMappingURL=extension.js.map