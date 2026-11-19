import {studies,runs} from '../api/research.js';
import {sequential} from '../api/sequential.js';
export const store={studies:[],runs:[],sessions:[],studyId:0,runId:0,sessionId:0,rows:[],session:null};
export async function load(){[store.studies,store.runs,store.sessions]=await Promise.all([studies.list(),runs.list(),sequential.list()]);if(!store.studyId)store.studyId=store.studies[0]?.id||0;}
export async function loadRows(){store.rows=store.studyId?await studies.rows(store.studyId):[];}
export async function loadSession(id){store.session=await sequential.get(id);store.sessionId=id;return store.session;}
