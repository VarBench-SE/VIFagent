import * as vscode from 'vscode';
import { execFile } from 'child_process';
import { Uri } from 'vscode';
import * as os from 'os';
import sharp from 'sharp';
import { v4 as uuidv4 } from 'uuid';

type Span = [number, number]; // Tuple of two integers
type Box2D = [number, number, number, number]; // Tuple of four floats

const SETTING_PATH = "/home/creux/Documents/AI/VIFagent/resources/plane/"

interface CodeImageMapping {
	spans: Span[];
	zone: Box2D;
}
type MappingWithScore = [CodeImageMapping, number];



let storedDecorations: { [key: string]: vscode.TextEditorDecorationType } = {};  // Object to store decoration types by a unique identifier
let storedRanges: { [key: string]: vscode.Range[] } = {};  // Object to store ranges by the same identifier

import * as path from 'path';
function getEditorForDocument(doc: vscode.TextDocument): vscode.TextEditor | undefined {
	return vscode.window.visibleTextEditors.find(editor => editor.document === doc);
}

type RGB = [number, number, number];

async function drawBoxes(
	imagePath: string,
	boxescolors: [Box2D, RGB][]
) {


	let tmpImagePathName = path.join(os.tmpdir(), uuidv4() + ".png");
	const tmpImagePath = await copyToTemp(imagePath, tmpImagePathName);


	const svgs: sharp.OverlayOptions[] = []

	const image = sharp(imagePath)
	const medatada = await image.metadata()
	boxescolors.forEach(boxcolor => {

		const box = boxcolor[0]
		const color = boxcolor[1]

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

		svgs.push({ input: Buffer.from(svg), top: 0, left: 0 })
	});

	await sharp(tmpImagePath.fsPath)
		.composite(svgs)
		.toFile(imagePath);

}

async function copyToTemp(sourcePath: string, existingFilePath: string): Promise<vscode.Uri> {
	const sourceUri = vscode.Uri.file(sourcePath);
	const targetUri = vscode.Uri.file(existingFilePath);
	await vscode.workspace.fs.copy(sourceUri, targetUri, { overwrite: true });
	return targetUri;
}


export function activate(context: vscode.ExtensionContext) {
	console.log("Extension activated"); // Add this


	let disposable = vscode.commands.registerCommand('tikz-mapped.run-mapped', async () => {

		//creating the dummy editing file from the existing one (hardcoded path)
		const filePath = path.join(SETTING_PATH,'code.tex');
		const imageFilePath = await copyToTemp(path.join(SETTING_PATH,'image.png'), path.join(os.tmpdir(), "image.png"));

		//Opening the image and the code side to side
		const doc = await vscode.workspace.openTextDocument(filePath);
		await vscode.window.showTextDocument(doc, vscode.ViewColumn.One);

		await vscode.commands.executeCommand(
			'vscode.open',
			vscode.Uri.file(imageFilePath.fsPath),
			vscode.ViewColumn.Two
		);

		if (doc == undefined) {
			vscode.window.showErrorMessage(`Error: file not found`);
			return
		}

		const editor = getEditorForDocument(doc)
		if (editor == undefined) {
			vscode.window.showErrorMessage(`Error: editor undefined`);
			return
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
		const script_path = context.asAbsolutePath('get_mapping.sh')
		const pickle_path = path.join(SETTING_PATH,"p.pickle")

		execFile(script_path, [pickle_path, `"${input}"`], async (error, stdout, stderr) => {
			if (error) {
				vscode.window.showErrorMessage(`Error: ${error.message}`);
				return;
			}
			if (stderr) {
				vscode.window.showWarningMessage(`Stderr: ${stderr}`);
			}
			vscode.window.showInformationMessage(`Output: ${stdout}`);


			const parsed: [CodeImageMapping, [number]][] = JSON.parse(stdout);

			const mappings: MappingWithScore[] = parsed.map(([mapping, [score]]): MappingWithScore => {
				return [
					{
						spans: mapping.spans as Span[],
						zone: mapping.zone as Box2D,
					},
					score as number,

				];
			});

			const mappings_max = Math.max(...mappings.map(mappingwscore => {
				return mappingwscore[1]
			}))


			//coloring the code and adding the rectangles on the image
			const boxescolors: [Box2D, RGB][] = []
			const uniquespans_rangescolors: Map<string, [Span[], RGB]> = new Map()

			//reversedso that the highest probable boxes are written over the other ones
			mappings.reverse().forEach(async (mapping, index) => {

				const adjusted_mapping = (((mapping[1] / mappings_max) ** 0.3) * 2) - 1
				let red = 0
				let blue = 0
				if (adjusted_mapping > 0) {
					blue = (150 + 105 * adjusted_mapping)
				} else {
					red = (150 + 105 * (-adjusted_mapping))
				}

				const key = mapping[0].spans.map(span => String(span[0]) + String(span[1])).join("")


				uniquespans_rangescolors.set(key,[mapping[0].spans, [red,0 , blue]])


				const zone = mapping[0].zone
				boxescolors.push([zone, [red, 0, blue]])
			})
			await drawBoxes(imageFilePath.fsPath, boxescolors)

			//adding decorations
			uniquespans_rangescolors.forEach((rangecolor:[Span[], RGB],key:string) => {
					
					const ranges = rangecolor[0].map(s =>
						new vscode.Range(doc.positionAt(s[0]), doc.positionAt(s[1]))
					);
					
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

export function deactivate() {
	for (const key in storedDecorations) {
		if (storedDecorations[key]) {
			storedDecorations[key].dispose();
		}
	}
}

function clearAllDecorations(editor: vscode.TextEditor) {
	for (const key in storedDecorations) {
		if (storedDecorations[key]) {
			editor.setDecorations(storedDecorations[key], []);
			storedDecorations[key].dispose();
		}
	}
	storedDecorations = {};
	storedRanges = {};
}
